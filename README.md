# legotrain
Python scripts to support Lego City trains

This package depends on https://github.com/undera/pylgbst 

Example of computer control using this software. The entire sequence is done 
with hands off, although the handset controller remains fully functional. 
https://www.youtube.com/watch?v=AUTcSPW_DJ4

## Design

In the configuration currently implemented, two trains equipped with
down-facing vision sensors run on a simple oval track equipped with
two lateral branches that serve as train stations, each one dedicated 
to its own train. The trains run against each other, and the software
takes care of preventing collisions by ensuring that they can only
cross each other when one is parked on, or moving towards, its own
station. Switches that connect the station branch with the main line
are fixed. 

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
the track at their extremities, in such a way that a train, when moving over a tiled 
stretch, will send a signal to the controlling script, so it can know where the train 
is at that moment, and take actions accordingly. The station segments differ slightly
from that configuration, by having a single red tile marking the point where the train
should stop when arriving at the station.

