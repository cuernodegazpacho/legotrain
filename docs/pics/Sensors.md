# Vision sensor placement

Sensor placement greatly affects their performance. The main factor is the distance the
sensor sits from the colored tiles. Ambient ligth can also affect their performance.  

I used LEGO® part #6254807 (Plate 2X2 Angle) as a mounting bracket:

| <img src="docs/pics/Angle.jpg" width="250"></img> |

#### Vision sensor mounted on a 60197 train engine

| <img src="docs/pics/DSC00921.jpeg" width="250"></img> |
  <img src="docs/pics/DSC00923a.jpeg" width="250"></img> |
  <img src="docs/pics/DSC00928a.jpeg" width="250"></img> |

#### Vision sensor mounted on a 60336 cargo train engine

This particular engine requires some modifications since the hub box sits at the'
very center of the engine, and thus blocks both access holes on the main structural
plate. The hub must be mounted offseted to the back, leaving the front hole uncovered.
The protruding sensor below the plate also needs special finish. The front
wheels carriage, being longer than in train 60197, can bump on the sensor when on
a curved track. The standard LEGO® curved track works OK, but non-standard third-party
tracks may cause a problem. 

| <img src="docs/pics/IMG_0026.jpg" width="250"></img> |
| <img src="docs/pics/IMG_0027.jpg" width="250"></img> |
  <img src="docs/pics/IMG_0029.jpeg" width="250"></img> |

All numerical parameters used in the color sensing software were derived with the sensors
mounted that way. Because of the high sensitivity to distance, these values won't work
well when sensors are mounted using other parts to hold them, even with slight different 
distances.

Mounting sensors fully recessed inside the train decreases their sensitivity and signal-to-noise 
ratio by a significant amount, rendering color signal detection very unreliable.

Vision sensors should be connected to Port B on the Powered UP hub.

This video by [BrickGuy](https://www.youtube.com/@brickguy) shows a way to mount sensors:

https://www.youtube.com/watch?v=S83go28JEiU


