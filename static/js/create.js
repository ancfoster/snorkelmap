// ── CONFIG
const MAPBOX_TOKEN = 'pk.eyJ1Ijoic25vcmtlbG1hcCIsImEiOiJjbWEzcTdyaXgxNzZ1MmlzZmR4dHRqNHVrIn0.TwWl3IRXS6uol-H36oZDDQ';

const ZOOM_THRESHOLD     = 15.6;
const ZOOM_MAX           = 18.5;
const ZOOM_MIN           = 4;
const ZOOM_THRESHOLD_PCT = ((ZOOM_THRESHOLD - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)) * 100;


// IndexedDB — local photo storage dor drafts
const DB_NAME     = 'SnorkelMapDB';
const DB_VERSION  = 1;
const PHOTO_STORE = 'photos';

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

// STATE
const state = {
  currentStep: 0,
  coordinates: null,
  locationMeta: { country: '', region: '', town: '' },
  locationConfirmed: false,
  name: '', alternateNames: [],
  overallDescription: '', surfaceDescription: '', underwaterDescription: '',
  accessType: new Set(), waterType: new Set(), difficulty: 1,
  envReef: new Set(), envRocky: new Set(), envSeabed: new Set(),
  envVegetated: new Set(), envStructures: new Set(), envGeological: new Set(),
  mlFish: new Set(), mlMammals: new Set(), mlCrustaceans: new Set(),
  mlMolluscs: new Set(), mlEchinoderm: new Set(), mlCnidarians: new Set(),
  mlReptiles: new Set(), mlCephalopods: new Set(), mlSessile: new Set(), mlBirds: new Set(),
  marineLifeComments: '',
  hazCurrents: new Set(), hazCurrentsComments: '',
  hazEntryExit: new Set(), hazEntryExitComments: '',
  hazWater: new Set(), hazWaterComments: '',
  hazTraffic: new Set(), hazTrafficComments: '',
  hazPollution: new Set(), hazPollutionComments: '',
  hazMarineLife: new Set(), hazMarineLifeComments: '',
  hazardsComments: '',
  facWashing: new Set(), facWashingComments: '',
  facFood: new Set(), facFoodComments: '',
  facParking: new Set(), facParkingComments: '',
  facTransport: new Set(), facTransportDescription: '',
  facSafety: new Set(), facSafetyComments: '',
  facEquipment: new Set(), facEquipmentComments: '',
  facOther: '',
  surfacePhotos: [],
  underwaterPhotos: [],
};


let map = null;
let mapInitialised = false;
let searchDebounceTimer = null;


// Local drafts
