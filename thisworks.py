from pypylon import pylon
import cv2
import time
import json
import os
from datetime import datetime

def main():

    #PYLON_RT = r"C:\Program Files\Basler\pylon 8\Runtime\win32"

    #os.environ["PYLON_GENICAM_GENTL64_PATH"] = PYLON_RT        # <- .cti files
    #os.add_dll_directory(PYLON_RT)                             # <- .dll files (Python 3.8+)

    factory = pylon.TlFactory.GetInstance()
    devices = factory.EnumerateDevices()

    if not devices:
        print("No camera devices found!")
        return

    for i, d in enumerate(devices):
        print(f"Camera {i}: {d.GetModelName()} - {d.GetSerialNumber()}")

    camera = pylon.InstantCamera(factory.CreateDevice(devices[0]))

    desired_fps = 30.0 # Desired frame rate in FPS, not exact due to floating point differences 
    base_output_folder = "camera_output"  # Base folder for all recordings
    os.makedirs(base_output_folder, exist_ok=True) # make dir if it doesn't exist
    camera.Open() 

    try:
        # For GigE cameras, use ResultingFrameRateAbs
        camera.AcquisitionFrameRateEnable.Value = True
        camera.AcquisitionFrameRateAbs.Value = desired_fps
        actual_fps = camera.ResultingFrameRateAbs.Value
    except Exception as e:
        print(f"Error setting frame rate: {e}")
        try:
            # For USB cameras, use ResultingFrameRate
            camera.AcquisitionFrameRate.Value = desired_fps
            actual_fps = camera.ResultingFrameRate.Value
        except Exception as e:
            print(f"Error setting USB frame rate: {e}")
            try:
                # For newer cameras, use BslResultingAcquisitionFrameRate
                camera.AcquisitionFrameRate.Value = desired_fps
                actual_fps = camera.BslResultingAcquisitionFrameRate.Value
            except Exception as e:
                print(f"Error setting BSL frame rate: {e}")
                actual_fps = desired_fps

    width = camera.Width.Value
    height = camera.Height.Value
    print(f"Camera ready. Image size: {width}x{height}")
    print("Press 's' to start recording")
    print("Press 'q' to stop recording and quit")
    
    # Start camera grabbing but don't record yet
    camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    recording = False
    frame_count = 0
    frame_timestamps = []
    video_writer = None
    start_time_ms = None
    timestamp = None
    start_frame_path = None
    end_frame_path = None
    output_folder = None
    
    while camera.IsGrabbing():
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if grabResult.GrabSucceeded():
            image = grabResult.Array
            cv2.imshow("Camera Feed", image)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('s') and not recording:
                # Create new folder with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_folder = os.path.join(base_output_folder, timestamp)
                os.makedirs(output_folder, exist_ok=True)
                print(f"Created new recording folder: {output_folder}")

                # Start recording
                recording = True
                video_filename = os.path.join(output_folder, "output.avi")
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                video_writer = cv2.VideoWriter(video_filename, fourcc, actual_fps, (width, height))
                start_time_ms = int(time.time() * 1000)
                frame_count = 0
                frame_timestamps = []
                print(f"Recording started at {start_time_ms} ms")
                
                # Save first frame
                start_frame_path = os.path.join(output_folder, "start_frame.png")
                cv2.imwrite(start_frame_path, image)
            
            if recording:
                video_writer.write(image)
                current_time_ms = int(time.time() * 1000)
                frame_timestamps.append((frame_count, current_time_ms))
                frame_count += 1
            
            if key == ord('q'):
                if recording:
                    # Save last frame
                    end_frame_path = os.path.join(output_folder, "end_frame.png")
                    cv2.imwrite(end_frame_path, image)
                    end_time_ms = int(time.time() * 1000)
                    print(f"Recording ended at {end_time_ms} ms")
                    print(f"Total frames captured: {frame_count}")
                    
                    # Save metadata
                    metadata = {
                        "start_time_ms": start_time_ms,
                        "end_time_ms": end_time_ms,
                        "requested_fps": desired_fps,
                        "actual_fps": actual_fps,
                        "frame_width": width,
                        "frame_height": height,
                        "total_frames": frame_count,
                        "frame_timestamps": frame_timestamps,
                        "video_file": "output.avi",
                        "start_frame": "start_frame.png",
                        "end_frame": "end_frame.png"
                    }
                    
                    metadata_filename = os.path.join(output_folder, "metadata.json")
                    with open(metadata_filename, 'w') as f:
                        json.dump(metadata, f, indent=4)
                    print(f"Metadata saved to {metadata_filename}")
                break
            
        grabResult.Release()

    # Cleanup
    if video_writer is not None:
        video_writer.release()
    camera.StopGrabbing()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()