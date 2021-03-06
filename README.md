## UAV Sensor fusion Simulation (Final Year Project)



https://user-images.githubusercontent.com/12397823/170942886-acd0a1b2-4278-4500-8611-137f6cfa6819.mp4



This   is  a   simulation  of   a  UAV   with  stereo   and  depth   cameras
fitted  for  localization  purposes   using  `stereo_image_proc`.

![Manipulator with Camera](./captures/Screenshot_20220525_144958.png "Manipulator with
Camera")

![Depth Cloud in RVIZ](./captures/DEPTHCLOUD.png "Depth cloud in RVIZ")

### Usage

Tested on ros-noetic with Gazebo SIM and RVIZ

- Clone into repo into catkin workspace
- Add `./assets/navigate.world` to world directory in Aerial Manipulator project
- Apply patches in `./patches/` if necessary
- `roslaunch aerial_manipulation aerial_manipulator.launch paused:=true world:=navigate`
- launch rviz and select topics to visualize

Teleoperation instruction are available in original manipulator repo
You can use `stereo_view` from `stereo_image_proc` to check cameras

## Node Graph

![Node Graph](./captures/Node-Graph8.png "Node Graph")
