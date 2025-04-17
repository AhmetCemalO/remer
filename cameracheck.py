import cv2

# Try opening the first available camera (usually index 0)
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Failed to open camera with OpenCV (index 0)")
else:
    print("Camera opened successfully via OpenCV")
    print("Press 'q' to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        cv2.imshow("OpenCV Camera Test", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

