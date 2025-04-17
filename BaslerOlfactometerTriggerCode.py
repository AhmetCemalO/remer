import os, time, datetime, cv2
from pypylon import pylon, genicam

# ---------- camera open & trigger config ----------
cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
cam.Open()
nm = cam.GetNodeMap()
nm.GetNode("TriggerSelector").SetValue("AcquisitionStart")
nm.GetNode("TriggerMode").SetValue("On")
nm.GetNode("TriggerSource").SetValue("Line1")
nm.GetNode("TriggerActivation").SetValue("RisingEdge")
try:
    nm.GetNode("AcquisitionFrameRateEnable").SetValue(False)
except genicam.GenericException:
    pass

cam.StartGrabbing(pylon.GrabStrategy_OneByOne)

# ---------- output folder ----------
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = os.path.join("output", stamp)
os.makedirs(out_dir, exist_ok=True)

print("READY  pulse Line1 HIGH to take a photo (press 'q' to quit)")
cv2.namedWindow("Basler Preview", cv2.WINDOW_NORMAL)

count          = 0
flash_until_ms = 0           # when to stop drawing the overlay

try:
    while cam.IsGrabbing():
        try:
            res = cam.RetrieveResult(1000, pylon.TimeoutHandling_ThrowException)
        except genicam.TimeoutException:
            continue        # no trigger in last second – keep waiting

        if res.GrabSucceeded():
            frame = res.Array
            count += 1

            # ---- save frame ----
            fname = os.path.join(out_dir, f"frame_{count:05d}.png")
            cv2.imwrite(fname, frame)

            # ---- set overlay timer ----
            flash_until_ms = int(time.time()*1000) + 500   # 0.5s flash

        res.Release()

        # ---- show preview ----
        display = frame.copy() if 'frame' in locals() else None
        if display is not None:
            t_now = int(time.time()*1000)
            if t_now < flash_until_ms:
                cv2.putText(display, f"PHOTO #{count} saved",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            1.0, (255,0,0), 2, cv2.LINE_AA)
            cv2.imshow("Basler Preview", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    pass

cam.StopGrabbing()
cam.Close()
cv2.destroyAllWindows()
print(f"Finished  {count} photos saved to {out_dir}")
