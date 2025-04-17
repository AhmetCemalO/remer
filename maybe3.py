import os, time, datetime, csv, threading, queue, cv2
from pypylon import pylon, genicam

# ---------- tweakables ----------
QUEUE_LEN        = 200            # frames buffered
WINDOW_MS        = 12_000         # rotate files every 12 seconds
PULSE_WINDOW_MS  = 500            # green overlay time
# --------------------------------

def writer_worker(q: queue.Queue, out_dir: str):
    """Thread: save images + append rows to a CSV that rotates every 12s."""
    window_start = None
    csv_fh, writer = None, None
    img_dir = None                   # image subfolder for this window

    def open_new_window(ts_ms: float):
        nonlocal csv_fh, writer, img_dir, window_start
        if csv_fh:
            csv_fh.flush(); csv_fh.close()

        # human‑readable name:  HHMMSS_mmm  (mmm = ms)
        ts_tag = datetime.datetime.fromtimestamp(ts_ms/1000.0)\
                                   .strftime("%H%M%S_%f")[:-3]
        img_dir = os.path.join(out_dir, f"burst_{ts_tag}")
        os.makedirs(img_dir, exist_ok=True)

        csv_path = os.path.join(out_dir, f"burst_{ts_tag}.csv")
        csv_fh   = open(csv_path, "w", newline="")
        writer   = csv.writer(csv_fh)
        writer.writerow(["frame_id", "timestamp_ms", "filename"])
        window_start = ts_ms
        return csv_fh, writer, img_dir, window_start

    # wait for first frame before opening files
    while True:
        item = q.get()
        if item is None:
            break
        fid, ts_ms, frame = item
        if window_start is None or (ts_ms - window_start) >= WINDOW_MS:
            csv_fh, writer, img_dir, window_start = open_new_window(ts_ms)

        fname = f"frame_{fid:06d}.png"
        cv2.imwrite(os.path.join(img_dir, fname), frame)
        writer.writerow([fid, f"{ts_ms:.3f}", os.path.join(os.path.basename(img_dir), fname)])
        q.task_done()

    if csv_fh:
        csv_fh.flush(); csv_fh.close()
    print("[writer] done , all images & CSV rows flushed")


def main():
    # ---------- camera config ----------
    cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    cam.Open()
    nm = cam.GetNodeMap()
    nm.GetNode("TriggerSelector").SetValue("FrameStart")
    nm.GetNode("TriggerMode").SetValue("On")
    nm.GetNode("TriggerSource").SetValue("Line1")       # Arduino pulses
    nm.GetNode("TriggerActivation").SetValue("RisingEdge")
    try:
        nm.GetNode("AcquisitionFrameRateEnable").SetValue(False)
    except genicam.GenericException:
        pass
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    # ------------------------------------

    # ---------- output paths ----------
    stamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join("output", stamp)
    os.makedirs(out_dir, exist_ok=True)

    q = queue.Queue(QUEUE_LEN)
    t = threading.Thread(target=writer_worker, args=(q, out_dir), daemon=True)
    t.start()

    cv2.namedWindow("Basler Preview", cv2.WINDOW_NORMAL)
    count, flash_until = 0, 0
    dummy = None

    try:
        while cam.IsGrabbing():
            grab = cam.RetrieveResult(1000, pylon.TimeoutHandling_Return)
            if grab and grab.GrabSucceeded():
                frame = grab.Array
                # use camera’s own µs timestamp if available
                try:
                    ts_ms = grab.TimeStamp / 1000.0
                except AttributeError:
                    ts_ms = time.time()*1000
                count += 1
                q.put((count, ts_ms, frame))          # hand off to writer
                flash_until = time.time()*1000 + PULSE_WINDOW_MS
                dummy = frame                         # show latest

            # ---- UI update, even if no new frame ----
            if dummy is not None:
                disp = dummy.copy()
                if time.time()*1000 < flash_until:
                    cv2.putText(disp, f"#{count}", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                cv2.imshow("Basler Preview", disp)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cam.StopGrabbing();  cam.Close()
        q.put(None)        # tell writer to finish
        t.join()
        cv2.destroyAllWindows()
        print(f"[main] finished , {count} frames captured to {out_dir}")

if __name__ == "__main__":
    main()
