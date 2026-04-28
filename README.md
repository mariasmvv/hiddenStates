# hiddenStates
System for decoding latent decision variables from facial expressions

The Unity Game scripts are:
- GamaManager:
- ForagingUI: has all the UI code
- Orbmanager: contains the probabilities of reward and depletion of each orb
- PupilBridgeClient:
- TownLevelManager:
- Vrpickaxe:

The Python Scripts:
- Bridge:
  Run it on your laptop before launching the game: it connects to the Pupil Companion app, continuously estimates the clock difference between the two devices, and exposes a local HTTP API on port 8765. Unity uses this to align its clock with the eye-tracker (sync), check that the bridge is running (status), and stamp named events into the recording at precise timestamps (event). This will let in-game moments be accurately matched to gaze data later.
  
- Post Processing:
  This script takes a completed VR session folder and processes it into analysis-ready outputs. It reads the trial data exported from Unity and the eye-tracking data exported from Pupil, matches every gaze sample to the game event that was active at that moment, and writes an annotated copy of the world camera video with the current event and elapsed time overlaid on each frame. All outputs land in a derived/ subfolder alongside the raw data.
