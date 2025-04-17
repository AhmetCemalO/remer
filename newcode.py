import cv2
import json
import os
import time
from datetime import datetime
from pypylon import pylon

class BaslerHardwareTriggerCamera:
    def __init__(
        self,
        trigger_line="Line0",
        trigger_activation="RisingEdge",
        exposure_time_us=10000,  # 10 ms
        output_folder="hardware_trigger_output",
        estimated_trigger_fps=50.0,
        camera_index=0
    ):
        """
        Constructor for a hardware-triggered Basler camera.
        
        :param trigger_line: Which physical line is used for external trigger (e.g. 'Line0')
        :param trigger_activation: 'RisingEdge' or 'FallingEdge'
        :param exposure_time_us: Exposure time in microseconds (default: 10000 = 10 ms)
        :param output_folder: Folder where video + metadata will be saved
        :param estimated_trigger_fps: The approximate frequency of incoming trigger signals
        :param camera_index: If you have multiple cameras, which index to open (0 = first device)
        """
        self.trigger_line = trigger_line
        self.trigger_activation = trigger_activation
        self.exposure_time_us = exposure_time_us
        self.output_folder = output_folder
        self.estimated_trigger_fps = estimated_trigger_fps
        self.camera_index = camera_index

        # Pylon camera handle
        self.camera = None
        self.video_writer = None
        self.recording = False
        self.frame_count = 0
        self.record_start_time = None
        self.last_frame_time = None
        self.timestamp_str = None
        self.video_filename = None
        self.metadata = {}
        
    def setup_camera(self):
        """
        Opens the camera, sets hardware trigger mode, exposure, etc.
        """
        # 1) Create camera instance
        self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        self.camera.Open()

        # 2) Enable hardware trigger on the specified line
        self.camera.TriggerMode.SetValue("On")
        self.camera.TriggerSource.SetValue(self.trigger_line)
        self.camera.TriggerActivation.SetValue(self.trigger_activation)

        # 3) Set exposure time
        self.camera.ExposureTimeAbs.SetValue(float(self.exposure_time_us))

        # 4) Set acquisition mode to Continuous for repeated triggers
        self.camera.AcquisitionMode.SetValue("Continuous")

        # 5) Optional: If you want chunk data for precise camera-side timestamps
        #    (Then you'd read out chunk data from each frame.)
        # self.camera.ChunkModeActive.SetValue(True)
        # self.camera.ChunkSelector.SetValue("Timestamp")
        # self.camera.ChunkEnable.SetValue(True)

        # 6) Start grabbing
        self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
    
    def start_recording(self):
        """
        Start recording frames to a new folder.
        """
        if not self.camera or not self.camera.IsOpen():
            raise RuntimeError("Camera not open. Call setup_camera() first.")

        if not self.recording:
            self.timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_path = os.path.join(self.output_folder, self.timestamp_str)
            os.makedirs(folder_path, exist_ok=True)

            self.video_filename = os.path.join(folder_path, "output.avi")
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            w = int(self.camera.Width.Value)
            h = int(self.camera.Height.Value)

            # We guess the FPS for the video container. (Not super critical; it's just for playback.)
            self.video_writer = cv2.VideoWriter(self.video_filename, fourcc, self.estimated_trigger_fps, (w, h))

            self.frame_count = 0
            self.record_start_time = time.time()
            self.recording = True

            print(f"Recording started. Output folder: {folder_path}")

    def stop_recording(self):
        """
        Stop recording, finalize metadata, close video writer.
        """
        if self.recording:
            elapsed = time.time() - self.record_start_time
            self.recording = False

            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None

            # Save metadata
            folder_path = os.path.join(self.output_folder, self.timestamp_str)
            metadata_file = os.path.join(folder_path, "metadata.json")
            self.metadata["camera_model"] = self.camera.DeviceModelName.GetValue()
            self.metadata["trigger_line"] = self.trigger_line
            self.metadata["exposure_time_us"] = self.exposure_time_us
            self.metadata["estimated_trigger_fps"] = self.estimated_trigger_fps
            self.metadata["frame_count"] = self.frame_count
            self.metadata["record_duration_s"] = elapsed
            self.metadata["video_file"] = "output.avi"
            
            with open(metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=4)
            
            print(f"Stopped recording. {self.frame_count} frames captured.")
            print(f"Metadata saved to: {metadata_file}")

    def grab_frames(self, display_window=True):
        """
        Main loop to grab frames from the camera. 
        This should be called repeatedly (e.g. in while camera.IsGrabbing() loop).
        """
        if not self.camera or not self.camera.IsGrabbing():
            return

        # If there's a triggered frame, RetrieveResult() will give it.
        # If no trigger arrived, it may block until the next one or time out.
        grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        if grab_result.GrabSucceeded():
            image = grab_result.Array

            # If the camera is in Monochrome, you might want to convert to BGR for saving in color
            # image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) # If needed

            # Display if needed
            if display_window:
                cv2.imshow("Camera Feed", image)
                cv2.waitKey(1)  # allow time for window refresh

            # If we're in recording mode, write to video
            if self.recording and self.video_writer:
                self.video_writer.write(image)
                self.frame_count += 1

                # For fine-grained timestamp logging:
                frame_timestamp_ms = int(time.time() * 1000)
                self.metadata.setdefault("frame_timestamps", []).append({
                    "frame_index": self.frame_count,
                    "host_time_ms": frame_timestamp_ms
                })

        grab_result.Release()

    def close_camera(self):
        """
        Cleanup method to stop grabbing, close the camera, destroy windows.
        """
        if self.camera and self.camera.IsGrabbing():
            self.camera.StopGrabbing()
        if self.camera and self.camera.IsOpen():
            self.camera.Close()
        cv2.destroyAllWindows()

def main():
    # 1) Instantiate your camera handler with desired parameters
    cam_handler = BaslerHardwareTriggerCamera(
        trigger_line="Line0",         # the line used for the external trigger
        trigger_activation="RisingEdge",
        exposure_time_us=10000,       # 10 ms
        output_folder="hardware_trigger_output",
        estimated_trigger_fps=50.0    # used for the AVI container
    )

    # 2) Setup the camera for hardware triggers
    cam_handler.setup_camera()

    print("Press 's' to start recording. Press 'q' to stop and exit.")
    
    while True:
        # Grab any available triggered frames
        cam_handler.grab_frames(display_window=True)

        # Keyboard control to simulate external start/stop
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            cam_handler.start_recording()
        elif key == ord('q'):
            cam_handler.stop_recording()
            break

    cam_handler.close_camera()

if __name__ == "__main__":
    main()
