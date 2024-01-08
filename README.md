# legotrain
Python scripts to support Lego City trains

This package depends on https://github.com/undera/pylgbst 

Example of computer control using this software. The entire sequence is done 
with hands off, although the handset controller remains fully functional. 
https://www.youtube.com/watch?v=AUTcSPW_DJ4

## Design

In the configuration currently implemented, two trains equipped with
vision sensors (LEGO® Powered Up 88007 Color & Distance Sensor) 
run on a simple (topologically) circular track equipped with  two lateral 
branches that serve as train stations, each one dedicated to its own 
train. The trains run against each other, and the software takes care 
of preventing collisions by ensuring that they can only cross each 
other when one is parked on, or moving towards, its own station. 
Switches that connect the station branch with the main line are fixed. 

### Trains

Each train in the system is represented by an instance of a subclass of 
_Train_. The specific subclass capable of handling the vision sensor is
_SmartTrain_. The corresponding module _train.py_ contains class definitions 
for these, as well as for auxiliary objects that are used to control the 
train's motors, their LED headlights (when so equipped), their hub's LED color 
light, and vision sensors mounted pointing down that are used to detect 
color tiles on the track.

Other classes exist to handle a simple train with no vision sensor, but which
can optionally have LED headlights (_SimpleTrain_), and a composite train made
by linking back-to-back the two engines, with all cars in between (_CompoundTrain_).
Currentlly these may not work properly because most of the recent development
work focused on the two-train configuration. 

### Track

The track for this initial project is topologically a simple circle with
two branches that are used as train stations. Each one serves one 
sensor-equipped train. The track is divided into segments; the main goal of the
software is to ensure that each segment is occupied by mostly one, and only one,
train, at any given time. 

The simple track configuration described above can be divided into four segments;
two are associated with each one of the stations, and there are two other segments
laid out in between the stations. Segments are marked by color tiles laid out on
the track at each segment's ends, in such a way that a train, when moving over a color 
tile, will send a signal to the controlling script. That way, the script can know where 
the train is at that moment, and take actions accordingly. The station segments differ 
slightly from the above configuration, by having a single red tile marking the point 
where the train should stop when arriving at the station.

The segment classes and the track layout are defined in module _track.py_. There are 
two kinds of segments, a plain, and a structured segment. The structured segment has
two sub-segments inside it, named 'fast' and 'slow'. The transition between them is 
marked by a color tile of the same color used to mark the segment end points. The purpose
of the sub-segments is to allow the train to know where it is inside the segment, giving
it enough time to interrogate the next segment about its occupancy status, allowing it to
prepare in advance of arriving at the inter-segment transition region. Plain segments can
be used when no such advanced preparation is necesssary (as, for instance, when the next
segment in the track layout is a station segment where a mandatory stop has to take
place anyway).

The track layout is defined by a static data structure made of nested dictionaries. Two
track layouts are actually necessary, since the layout may look different for trains 
running in clockwise and counter-clockwise directions.

### Controller


### Vision sensors

The 88007 sensors have trouble in telling apart many of the colors available in LEGO 
bricks. We conducted many experiments with a variety of colors in order to select 
particular combinations that would work for our project. So far, we found just three
suitable colors: (color references here)

Even with these "best" colors, the sensors generate a significant number of false and
multiple detections, in part probably caused by interference with ambient light and the 
colors of the track sleepers and the carpet underneath, and sensor sampling resolution.
The code has a number of ways of, at least partially, handling these false and multiple
detections by relying on timing information as the train moves along the track. 

