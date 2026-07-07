Barcode Camera System

A Raspberry Pi–based image capture system that automatically photographs an item when its barcode is scanned.

The application continuously captures frames from a USB webcam while listening for input from a USB barcode scanner. When a barcode is scanned, the latest camera frame is saved using the barcode as the filename.

Designed for manufacturing, warehouse, and quality-control environments, the system runs unattended as a systemd service and is easily deployable to multiple Raspberry Pi devices.

Features
Automatic image capture on barcode scan
Continuous camera feed for minimal capture latency
Automatic filename generation using scanned barcode
Runs as a background systemd service
Modular Python architecture
Thread-safe camera capture
Logging via systemd journal
Prepared for Microsoft SharePoint integration
Easy deployment using install.sh
Hardware Requirements
Tested Hardware
Component	Model
Raspberry Pi	Raspberry Pi 4
Camera	Logitech C270 USB Webcam
Barcode Scanner	Datalogic QuickScan QD2430
Operating System	Raspberry Pi OS Bookworm
Software Requirements
Python 3
OpenCV
evdev
requests
msal (future SharePoint integration)
Project Structure
barcode_camera/
│
├── main.py                 # Application entry point
├── camera.py               # Camera handling
├── scanner.py              # Barcode scanner interface
├── storage.py              # Image storage / SharePoint upload
├── config.py               # Configuration
│
├── requirements.txt
├── install.sh
├── barcode_camera.service
│
└── README.md
Installation

Clone the repository:

git clone <repository-url>
cd barcode_camera

Make the installer executable:

chmod +x install.sh

Run the installer:

./install.sh

The installer will:

Install required packages
Create a Python virtual environment
Install Python dependencies
Install the systemd service
Enable automatic startup
Start the application
Wiring
Camera

Connect the Logitech C270 to any available USB port.

Verify detection:

ls /dev/video*

Expected output:

/dev/video0
Barcode Scanner

Connect the Datalogic QuickScan QD2430 via USB.

Verify detection:

cat /proc/bus/input/devices

Expected output should include:

Datalogic ADC Inc. Handheld Barcode Scanner

Determine the stable device path:

ls -l /dev/input/by-id/

Configure the scanner device in config.py.

Example:

SCANNER_DEVICE = "/dev/input/by-id/usb-Datalogic_ADC_Inc._Handheld_Barcode_Scanner-event-kbd"

Using the /dev/input/by-id path is recommended because it remains stable across reboots.

Configuration

Application settings are stored in config.py.

Example:

CAMERA_INDEX = 0

SCANNER_DEVICE = "/dev/input/by-id/..."

LOCAL_SAVE_DIR = "/home/pi/Production_Photos"

ENABLE_SHAREPOINT = False

Future SharePoint settings:

SHAREPOINT = {
    "tenant_id": "",
    "client_id": "",
    "client_secret": "",
    "site_id": "",
    "drive_id": ""
}
Running the Application

To run manually:

python3 main.py

Normally the application is started automatically by systemd.

Service Management

Check status:

sudo systemctl status barcode_camera.service

Restart:

sudo systemctl restart barcode_camera.service

Stop:

sudo systemctl stop barcode_camera.service

Start:

sudo systemctl start barcode_camera.service

Enable automatic startup:

sudo systemctl enable barcode_camera.service

Disable automatic startup:

sudo systemctl disable barcode_camera.service
Logging

View the live application log:

journalctl -u barcode_camera.service -f

View the last 100 log entries:

journalctl -u barcode_camera.service -n 100
Updating

Pull the latest version:

git pull

Re-run the installer:

./install.sh

The installer safely updates the service without requiring manual configuration.

Troubleshooting
Camera not detected

Check:

ls /dev/video*

If no camera is listed:

Verify the USB connection.
Test with another USB port.
Verify camera functionality using another application.
Scanner not detected

Check:

cat /proc/bus/input/devices

Verify that the scanner appears.

Then verify:

ls -l /dev/input/by-id

Update SCANNER_DEVICE if necessary.

Images are not saved

Check:

Camera service is running.
LOCAL_SAVE_DIR exists.
Disk has available space.
Application logs for errors.
Service will not start

Check status:

sudo systemctl status barcode_camera.service

Then inspect the log:

journalctl -u barcode_camera.service
Future Roadmap
Microsoft Graph integration
Automatic SharePoint uploads
Offline upload queue with retry
Image upload status reporting
Multiple camera support
Configuration file (YAML)
Automatic software updates
Centralized fleet management
License

Specify your preferred license here.

Examples:

MIT
Apache 2.0
Proprietary (Internal Company Use)
