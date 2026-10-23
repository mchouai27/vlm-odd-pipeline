# ODD evaluation attributes

The stage-wise annotation evaluation covers these **21 attributes**:

1. NumberOfLanes
2. Crossroads
3. PedestrianCrossings
4. Divided
5. Undivided
6. BarriersOnEdges
7. StreetFurniture
8. ShoulderGrass
9. ShoulderPaved
10. SolidBarriers
11. Parking
12. RadialRoads
13. Cloudiness
14. Illumination
15. NonPrecipitatingWaterDroplets
16. StandingWater
17. VolumeOfTraffic
18. DensityOfAgents
19. FlowRate
20. RoadWorks
21. TransversePlane

These evaluation attributes can represent fields or grouped values from the structured VLM output. See [`attribute_paths.example.json`](../configs/attribute_paths.example.json) for a source-path mapping template and the [annotation guide](annotation_guidelines.pdf) for labeling conventions.
