import os, time, datetime, cv2, numpy as np
from pypylon import pylon, genicam

# ---------- camera open & trigger config ----------
cam = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
cam.Open()
nm = cam.GetNodeMap()
nm.GetNode("TriggerSelector").SetValue("FrameStart")
nm.GetNode("TriggerMode").SetValue("On")
nm.GetNode("TriggerSource").SetValue("Line1")        # rising‑edge HW trigger
nm.GetNode("TriggerActivation").SetValue("RisingEdge")
try:   nm.GetNode("AcquisitionFrameRateEnable").SetValue(False)
except genicam.GenericException:   pass

cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)   # keeps newest frame in buffer

# ---------- output folder ----------
stamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = os.path.join("output", stamp)
os.makedirs(out_dir, exist_ok=True)

print("READY  pulse Line1 HIGH to take a photo (press 'q' to quit)")
cv2.namedWindow("Basler Preview", cv2.WINDOW_NORMAL)

# a black dummy image until the first trigger arrives
dummy   = np.zeros((int(cam.Height.Value), int(cam.Width.Value)), dtype=np.uint8)
display = dummy.copy()

count, flash_until_ms = 0, 0

while cam.IsGrabbing():
    grab = cam.RetrieveResult(10, pylon.TimeoutHandling_Return)   # 10 ms max wait

    if grab and grab.GrabSucceeded():            # got a new triggered frame 🔥
        display = grab.Array.copy()              # show it
        count  += 1
        cv2.imwrite(os.path.join(out_dir, f"frame_{count:05d}.png"), display)
        flash_until_ms = int(time.time()*1000) + 500   # 0.5 s overlay
        grab.Release()

    # ---- draw overlay & show whatever we have in "display" ----
    img = display.copy()
    if int(time.time()*1000) < flash_until_ms:
        cv2.putText(img, f"PHOTO #{count} saved", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,255,0), 2, cv2.LINE_AA)
    cv2.imshow("Basler Preview", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cam.StopGrabbing()
cam.Close()
cv2.destroyAllWindows()
print(f"Finished {count} photos saved to {out_dir}")
