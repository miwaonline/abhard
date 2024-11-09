import serial
import sys

# Function to configure the serial port

def configure_serial(port):
    try:
        ser = serial.Serial(
            port=port,
            baudrate=9600,
            timeout=1  # Non-blocking read with a timeout of 1 second
        )
        print(f"Connected to USB device on port {port}")
        return ser
    except serial.SerialException as e:
        print(f"Error: Could not open serial port {port}. {e}")
        sys.exit(1)

# Main function to continuously read data from USB

def main():
    # Replace 'COM3' with your actual port (for Windows, e.g., COM3) or '/dev/ttyUSB0' (for Linux)
    usb_port = 'COM3' if sys.platform == 'win32' else '/dev/scaner0'

    ser = configure_serial(usb_port)

    try:
        while True:
            if ser.in_waiting > 0:  # Check if data is available
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore').strip()
                if data:
                    print(f"Received: {data}")
    except KeyboardInterrupt:
        print("\nProgram interrupted. Closing connection.")
    finally:
        ser.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()

