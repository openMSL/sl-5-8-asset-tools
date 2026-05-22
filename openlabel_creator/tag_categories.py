"""Tag categorization for OpenLABEL vocabulary.

Maps tag type strings from OpenLABEL JSON to their target JSON-LD section
(Behaviour, RoadUser, or Odd) based on the ASAM OpenLABEL ontology structure.
"""

from __future__ import annotations

# Tags that map to openlabel:Behaviour section
BEHAVIOUR_TAGS: frozenset[str] = frozenset(
    {
        "MotionAccelerate",
        "MotionAway",
        "MotionCross",
        "MotionCutIn",
        "MotionCutOut",
        "MotionDecelerate",
        "MotionDrive",
        "MotionLaneChangeLeft",
        "MotionLaneChangeRight",
        "MotionOvertake",
        "MotionReverse",
        "MotionRun",
        "MotionSlide",
        "MotionStop",
        "MotionTowards",
        "MotionTurn",
        "MotionTurnLeft",
        "MotionTurnRight",
        "MotionUTurn",
        "MotionWalk",
        "BehaviourCommunication",
    }
)

# Tags that map to openlabel:RoadUser section
ROAD_USER_TAGS: frozenset[str] = frozenset(
    {
        "VehicleCar",
        "VehicleTruck",
        "VehicleBus",
        "VehicleMotorcycle",
        "VehicleBicycle",
        "VehicleTrailer",
        "VehicleVan",
        "VehicleOther",
        "HumanPedestrian",
        "HumanWheelchair",
        "HumanChild",
        "HumanOther",
        "AnimalLarge",
        "AnimalSmall",
        "AnimalOther",
        "RoadUserVehicle",
        "RoadUserHuman",
        "RoadUserAnimal",
    }
)

# Tags that map to openlabel:Odd section (everything else in the ontology)
ODD_TAGS: frozenset[str] = frozenset(
    {
        "DrivableAreaEdge",
        "DrivableAreaType",
        "DrivableAreaSurfaceType",
        "DrivableAreaSurfaceCondition",
        "DrivableAreaSurfaceFeature",
        "GeometryTransverse",
        "HorizontalCurves",
        "HorizontalStraights",
        "LaneSpecificationDimensions",
        "LaneSpecificationLaneCount",
        "LaneSpecificationMarking",
        "LaneSpecificationTravelDirection",
        "LaneSpecificationType",
        "LongitudinalDownSlope",
        "LongitudinalLevelPlane",
        "LongitudinalUpSlope",
        "SceneryFixedStructure",
        "ScenerySpecialStructure",
        "SceneryTemporaryStructure",
        "SceneryZone",
        "JunctionIntersection",
        "JunctionRoundabout",
        "SignsInformation",
        "SignsRegulatory",
        "SignsWarning",
        "ConnectivityCommunication",
        "ConnectivityPositioning",
        "IlluminationArtificial",
        "IlluminationCloudiness",
        "IlluminationLowLight",
        "DaySunElevation",
        "DaySunPosition",
        "WeatherRain",
        "WeatherSnow",
        "WeatherWind",
        "RainType",
        "EnvironmentParticulates",
        "ParticulatesDust",
        "ParticulatesMarine",
        "ParticulatesPollution",
        "ParticulatesVolcanic",
        "SubjectVehicleSpeed",
        "TrafficAgentDensity",
        "TrafficFlowRate",
        "TrafficSpecialVehicle",
        "TrafficVolume",
        "TrafficAgentType",
        "ParticulatesWater",
    }
)

# Mapping from boolean tag type to its corresponding numeric value property
VALUE_PROPERTIES: dict[str, str] = {
    "MotionAccelerate": "motionAccelerateValue",
    "MotionDecelerate": "motionDecelerateValue",
    "MotionDrive": "motionDriveValue",
    "HorizontalCurves": "horizontalCurvesValue",
    "IlluminationCloudiness": "illuminationCloudinessValue",
    "LaneSpecificationDimensions": "laneSpecificationDimensionsValue",
    "LaneSpecificationLaneCount": "laneSpecificationLaneCountValue",
    "LongitudinalDownSlope": "longitudinalDownSlopeValue",
    "LongitudinalUpSlope": "longitudinalUpSlopeValue",
    "DaySunElevation": "daySunElevationValue",
    "WeatherRain": "weatherRainValue",
    "WeatherSnow": "weatherSnowValue",
    "WeatherWind": "weatherWindValue",
    "SubjectVehicleSpeed": "subjectVehicleSpeedValue",
    "TrafficAgentDensity": "trafficAgentDensityValue",
    "TrafficFlowRate": "trafficFlowRateValue",
    "TrafficVolume": "trafficVolumeValue",
    "ParticulatesWater": "particulatesWaterValue",
}

# Tags that use enum values (from ontology)
ENUM_TAGS: frozenset[str] = frozenset(
    {
        "DrivableAreaEdge",
        "DrivableAreaType",
        "DrivableAreaSurfaceType",
        "DrivableAreaSurfaceCondition",
        "DrivableAreaSurfaceFeature",
        "GeometryTransverse",
        "LaneSpecificationTravelDirection",
        "LaneSpecificationType",
        "SceneryFixedStructure",
        "ScenerySpecialStructure",
        "SceneryTemporaryStructure",
        "SceneryZone",
        "JunctionIntersection",
        "JunctionRoundabout",
        "SignsInformation",
        "SignsRegulatory",
        "SignsWarning",
        "ConnectivityCommunication",
        "ConnectivityPositioning",
        "IlluminationArtificial",
        "IlluminationLowLight",
        "DaySunPosition",
        "RainType",
        "EnvironmentParticulates",
        "BehaviourCommunication",
        "RoadUserVehicle",
        "RoadUserHuman",
        "RoadUserAnimal",
        "TrafficAgentType",
    }
)

# Tags where the tag itself IS the enum value (e.g. VehicleCar → RoadUserVehicle)
ROAD_USER_VEHICLE_TYPES: frozenset[str] = frozenset(
    {
        "VehicleCar",
        "VehicleTruck",
        "VehicleBus",
        "VehicleMotorcycle",
        "VehicleBicycle",
        "VehicleTrailer",
        "VehicleVan",
        "VehicleOther",
    }
)

ROAD_USER_HUMAN_TYPES: frozenset[str] = frozenset(
    {
        "HumanPedestrian",
        "HumanWheelchair",
        "HumanChild",
        "HumanOther",
    }
)

ROAD_USER_ANIMAL_TYPES: frozenset[str] = frozenset(
    {
        "AnimalLarge",
        "AnimalSmall",
        "AnimalOther",
    }
)


def categorize_tag(tag_type: str) -> str | None:
    """Return the section name for a tag type, or None if unknown.

    Returns one of: 'Behaviour', 'RoadUser', 'Odd'.
    """
    if tag_type in BEHAVIOUR_TAGS:
        return "Behaviour"
    if tag_type in ROAD_USER_TAGS:
        return "RoadUser"
    if tag_type in ODD_TAGS:
        return "Odd"
    return None
