# Barcode Camera System

A Raspberry Pi–based image capture system that automatically photographs an item when its barcode is scanned.

The application continuously captures frames from a USB webcam while listening for input from a USB barcode scanner. When a barcode is scanned, the latest camera frame is saved using the barcode as the filename.

Designed for manufacturing, warehouse, and quality-control environments, the system runs unattended as a systemd service and is easily deployable to multiple Raspberry Pi devices.

### Features

- Automatic image capture on barcode scan  
- Continuous camera feed for minimal capture latency
- Automatic filename generation using scanned barcode  
- Runs as a background systemd service  
- Modular Python architecture  
- Thread-safe camera capture  
- Logging via systemd journal  
- Prepared for Microsoft SharePoint integration  
- Easy deployment using install.sh  

### Hardware Requirements  

Tested Hardware  
  
Raspberry Pi: Raspberry Pi 4  
Camera: Logitech C270 USB Webcam  
Barcode Scanner: Datalogic QuickScan QD2430  
Operating System: Raspberry Pi OS Bookworm  


### Software Requirements

Python 3  
OpenCV  
evdev  
requests  
msal (future SharePoint integration)  

### Project Structure

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
├── barcode_camera.service.in # Service template rendered by the installer
│  
└── README.md  

## Installation

Clone the repository:  

git clone <repository-url>  
cd barcode_camera  

Make the installer executable:  

chmod +x install.sh  

Run the installer:  

./install.sh  

The installer will:  

- Install required packages
- Create a Python virtual environment
- Install Python dependencies
- Install the systemd service
- Enable automatic startup
- Start the application when an existing configuration is present

Run the installer as the normal Pi account (for example `admin`), without putting
`sudo` before `./install.sh`. It uses sudo for system changes and configures the
service to run as that account, with access to the `video` and `input` groups.
The checkout and virtual environment must be owned by that account.

On a first installation, edit the newly created `config.yaml` before starting:

```sh
sudo systemctl start barcode_camera.service
```

The service template is rendered with the actual checkout path and installed as
`/etc/systemd/system/barcode_camera.service`. Re-running the installer stops the
existing service before updating dependencies, then installs and restarts it.
If installation fails after stopping it, fix the reported error and rerun the
installer; the service remains stopped during the failed update.

## Wiring

### Camera

Connect the Logitech C270 to any available USB port.  

Verify detection:  

ls /dev/video*  

Expected output:  

/dev/video0  

### Barcode Scanner  

Connect the Datalogic QuickScan QD2430 via USB.  

Verify detection:  

cat /proc/bus/input/devices  

Expected output should include:  

Datalogic ADC Inc. Handheld Barcode Scanner  

Determine the stable device path:  

ls -l /dev/input/by-id/  

Configure the scanner device in config.py.  

#### Example:

SCANNER_DEVICE = "/dev/input/by-id/usb-Datalogic_ADC_Inc._Handheld_Barcode_Scanner-event-kbd"  

Using the /dev/input/by-id path is recommended because it remains stable across reboots.  

## Configuration

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
## Running the Application

### Barcode validation

Barcodes must contain 1–128 ASCII characters, start with a letter or digit, and
use only letters, digits, dots, underscores, or hyphens. Leading zeros and the
text received from the scanner are preserved. Spaces, slashes, control characters,
and other punctuation are rejected rather than silently changed. Rejections are
logged and no photo is saved. Confirm representative production barcodes fit
these rules before deployment.

Scanner input longer than 128 characters is discarded in full until Enter; the
next scan starts with a clean buffer. Storage validates again and checks that
both final and temporary photo paths remain inside the configured image directory.

### Background uploads and offline recovery

Photos are saved locally before uploading. When Azure is enabled, a background
worker checks the configured local image directory at startup and every 30
seconds. Scanning does not wait for network requests. Saved `.png` files form the
persistent queue and are retried after connection failures or application restarts.
All existing `.png` files in that directory are included; use a dedicated directory
for production captures.

Files are written to `.pending` files first and renamed after the write completes.
Incomplete `.pending` files are never uploaded. Inspect any left after a crash
before removing them. Local PNGs are deleted only after a successful upload. If a
blob already exists, the worker compares its contents with the local file before
deleting the local copy. A mismatch remains queued and is logged for investigation.
This verification requires blob read permission as well as upload permission.

New filenames include a unique capture identifier before the existing timestamp;
barcode searches and the web dashboard's date extraction remain compatible on
the Raspberry Pi. With Azure disabled, captures remain local and no upload worker
starts. Monitor available disk space during prolonged outages.

Before deploying to all stations, test one Pi by disconnecting its network,
scanning several barcodes, restarting the application while offline, and restoring
the network. Confirm the same saved photos appear in Azure and only successfully
uploaded files disappear locally.

Queue tests can be run without Pi hardware or Azure credentials:

```sh
python -m unittest discover -s tests -v
```

To run manually:

python3 main.py

Normally the application is started automatically by systemd.

#### Service Management

Startup errors, scanner failures, unexpected scanner termination, and unexpected
camera capture-thread errors produce a nonzero exit status. Systemd retries after
five seconds, including while a disconnected scanner is unavailable. Normal
SIGTERM/SIGINT shutdown returns success; `systemctl stop` leaves the service stopped.
Upload outages and recoverable camera read failures use their own retry loops.

After deploying, unplug the scanner and check the journal for a failure followed
by restart attempts. Reconnect it and confirm scanning resumes. Reboot the Pi to
verify automatic startup, then confirm `systemctl stop` leaves it stopped.
This restart policy does not detect a camera driver stuck inside a blocking read.

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
#Logging

View the live application log:

journalctl -u barcode_camera.service -f

View the last 100 log entries:

journalctl -u barcode_camera.service -n 100
Updating

Pull the latest version:

git pull

Re-run the installer:

./install.sh

The installer updates the service without requiring manual configuration.

## Troubleshooting

### Camera disconnects and stale frames

Captures only use frames received within the last second. A failed frame read
immediately clears the cached image, so subsequent barcodes cannot reuse that
image. Scans without a fresh frame are rejected and logged; rescan the item after
the camera recovers. These scans are not queued for later capture because the
original item may no longer be in front of the camera.

After five consecutive read failures, the camera connection is reopened every
two seconds until it recovers. The same retry applies if the camera is unavailable
at startup. Prefer a stable device path in `config.yaml`, since video device
numbers may change after reconnecting. Use your camera's capture-device link from
`ls -l /dev/v4l/by-id/`. For the tested C270, for example:

```yaml
camera:
  device: "/dev/v4l/by-id/usb-046d_C270_HD_WEBCAM_200901010001-video-index0"
```

The optional `device` setting takes precedence over `index`; existing numeric
index configurations continue to work. Use the path reported by your own Pi.

Test on one Pi by unplugging the camera, scanning a barcode, reconnecting the
camera, and rescanning with a different item visible. Confirm no photo is saved
while disconnected and the next photo shows the new item. Also start the app
without the camera connected and confirm plugging it in restores capture.

If the driver blocks inside a frame read, the freshness check still rejects old
frames, but automatic reopening must wait for the driver call to return. Such a
hang may require restarting the application or device.

### Camera not detected

Check:

ls /dev/video*

If no camera is listed:

Verify the USB connection.
Test with another USB port.
Verify camera functionality using another application.

### Scanner not detected

Check:

cat /proc/bus/input/devices

Verify that the scanner appears.

Then verify:

ls -l /dev/input/by-id

Update SCANNER_DEVICE if necessary.

### Images are not saved

Check:

Camera service is running.  
LOCAL_SAVE_DIR exists.  
Disk has available space.  
Application logs for errors.  

### Service will not start  

Check status:

sudo systemctl status barcode_camera.service

Then inspect the log:

journalctl -u barcode_camera.service

## Future Roadmap
- Microsoft Graph integration
- Automatic SharePoint uploads
- Offline upload queue with retry
- Image upload status reporting
- Possible multiple camera support
- Configuration file (YAML)
- Automatic software updates
- Possible centralized fleet management

