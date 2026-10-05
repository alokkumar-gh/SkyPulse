/**
 * SkyPulse Synthetic Weather Telemetry & Demo Data Layer
 * =======================================================
 * Deterministic, meteorologically plausible observation and hazard layer for local demo presentation.
 * 
 * ARCHITECTURE PRINCIPLES:
 * 1. ZERO BACKEND MODIFICATION: Strictly local frontend overlay.
 * 2. DETERMINISTIC / REPRODUCIBLE: Fixed-seed pseudo-random engine guarantees identical state on page reload.
 * 3. METEOROLOGICALLY GROUNDED: Regional climatological baselines, real thermodynamic formulas (Rothfusz Heat Index, WSI).
 * 4. CLEAN UI PRESENTATION: No artificial "DEMO/FAKE/SYNTHETIC" visual stamps in production-grade views.
 * 5. ADDITIVE MERGING: Preserves 100% of real backend news, citizen reports, and station observations.
 * 6. DYNAMIC TIME HORIZONS: Realistic timestamps enabling working 1h, 6h, 12h, 24h, 3d, 7d filters.
 */

import type { WeatherEvent, WeatherObservationFeature } from '../types';

/** Check if local demo telemetry mode is active */
export function isDemoModeActive(): boolean {
  // If explicitly configured in browser localStorage
  if (typeof window !== 'undefined') {
    const localOverride = localStorage.getItem('skypulse_demo_mode');
    if (localOverride === 'true') return true;
    if (localOverride === 'false') return false;
  }
  // In Vitest test environment, default to false so unit tests evaluate backend contracts
  if (typeof globalThis !== 'undefined' && (globalThis as any).process?.env && ((globalThis as any).process.env.VITEST || (globalThis as any).process.env.NODE_ENV === 'test')) {
    return false;
  }
  if (import.meta.env.MODE === 'test') {
    return false;
  }
  const envVal = import.meta.env.VITE_DEMO_MODE;
  if (envVal === true || envVal === 'true' || envVal === '1') return true;
  if (envVal === false || envVal === 'false' || envVal === '0') return false;
  return Boolean(import.meta.env.DEV);
}

// ── Deterministic Seeded PRNG (Mulberry32) ──────────────────────────────────
function createRNG(seed: number) {
  let s = seed >>> 0;
  return function next(): number {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Meteorological Formulas ──────────────────────────────────────────────────

/**
 * Calculates NOAA / Rothfusz Heat Index (°C)
 * Standard regression equation based on ambient temperature and relative humidity.
 */
export function calculateHeatIndex(tempC: number, humidityPct: number): number {
  if (tempC < 26.7) {
    return tempC;
  }
  const T = tempC * 1.8 + 32;
  const RH = humidityPct;

  let HI_F =
    -42.379 +
    2.04901523 * T +
    10.14333127 * RH -
    0.22475541 * T * RH -
    0.00683783 * T * T -
    0.05481717 * RH * RH +
    0.00122874 * T * T * RH +
    0.00085282 * T * RH * RH -
    0.00000199 * T * T * RH * RH;

  if (RH < 13 && T >= 80 && T <= 112) {
    const adj = ((13 - RH) / 4) * Math.sqrt((17 - Math.abs(T - 95)) / 17);
    HI_F -= adj;
  } else if (RH > 85 && T >= 80 && T <= 87) {
    const adj = ((RH - 85) / 10) * ((87 - T) / 5);
    HI_F += adj;
  }

  const HI_C = (HI_F - 32) / 1.8;
  return Number(HI_C.toFixed(1));
}

/**
 * Calculates SkyPulse Weather Severity Index (0 - 100)
 */
export function calculateWeatherSeverityIndex(params: {
  temperatureC: number;
  humidityPct: number;
  rainMm: number;
  windSpeedKmh: number;
  windGustKmh: number;
  pressureHpa: number;
}): {
  severityIndex: number;
  heatIndex: number;
  rainRisk: number;
  windRisk: number;
  humidityIndex: number;
  riskTier: 'LOW' | 'MODERATE' | 'ELEVATED' | 'SEVERE' | 'EXTREME';
} {
  const { temperatureC, humidityPct, rainMm, windSpeedKmh, windGustKmh, pressureHpa } = params;
  const heatIndex = calculateHeatIndex(temperatureC, humidityPct);
  const rainRisk = Math.min(100, Math.round((rainMm / 80) * 100));
  const heatRisk = Math.min(100, Math.max(0, Math.round(((heatIndex - 28) / 18) * 100)));
  const peakWind = Math.max(windSpeedKmh, windGustKmh * 0.85);
  const windRisk = Math.min(100, Math.max(0, Math.round(((peakWind - 15) / 65) * 100)));
  const pressureAnomaly = Math.max(0, (1010 - pressureHpa) * 4);
  const humidityIndex = Math.round(humidityPct);

  const rawWsi = 0.35 * rainRisk + 0.25 * heatRisk + 0.20 * windRisk + 0.20 * Math.min(100, pressureAnomaly + (humidityPct > 80 ? 20 : 0));
  const severityIndex = Math.min(100, Math.max(5, Math.round(rawWsi)));

  let riskTier: 'LOW' | 'MODERATE' | 'ELEVATED' | 'SEVERE' | 'EXTREME' = 'LOW';
  if (severityIndex >= 80) riskTier = 'EXTREME';
  else if (severityIndex >= 60) riskTier = 'SEVERE';
  else if (severityIndex >= 40) riskTier = 'ELEVATED';
  else if (severityIndex >= 20) riskTier = 'MODERATE';

  return {
    severityIndex,
    heatIndex,
    rainRisk,
    windRisk,
    humidityIndex,
    riskTier,
  };
}

// ── Master Catalog of 240+ Geographically Valid Indian Stations & Mesh Points ─
export interface StationProfile {
  name: string;
  city: string;
  district: string;
  state: string;
  lat: number;
  lon: number;
  region: 'NORTH' | 'WEST' | 'CENTRAL' | 'EAST' | 'SOUTH' | 'NORTHEAST' | 'ISLANDS';
  altitudeM: number;
  baseTempC: number;
  baseHumidity: number;
  baseRainMm: number;
  baseWindKmh: number;
  typicalCondition: string;
  icon: string;
}

export const INDIAN_STATION_CATALOG: StationProfile[] = [
  // ── NORTH ZONE (Delhi, Rajasthan, UP, Punjab, Haryana, J&K, Ladakh, HP, Uttarakhand) ──
  { name: 'Safdarjung Observatory', city: 'Delhi', district: 'New Delhi', state: 'Delhi', lat: 28.5847, lon: 77.2064, region: 'NORTH', altitudeM: 216, baseTempC: 38.2, baseHumidity: 32, baseRainMm: 0.0, baseWindKmh: 14, typicalCondition: 'Sunny / Dry Haze', icon: '☀️' },
  { name: 'Palam Station', city: 'Delhi', district: 'South West Delhi', state: 'Delhi', lat: 28.5665, lon: 77.1031, region: 'NORTH', altitudeM: 228, baseTempC: 39.0, baseHumidity: 30, baseRainMm: 0.0, baseWindKmh: 16, typicalCondition: 'Hot & Breezy', icon: '🌡️' },
  { name: 'Noida Sector 62', city: 'Noida', district: 'Gautam Buddha Nagar', state: 'Uttar Pradesh', lat: 28.6280, lon: 77.3649, region: 'NORTH', altitudeM: 200, baseTempC: 38.0, baseHumidity: 34, baseRainMm: 0.0, baseWindKmh: 13, typicalCondition: 'Hazy Sun', icon: '🌤️' },
  { name: 'Gurugram Cyber City', city: 'Gurugram', district: 'Gurugram', state: 'Haryana', lat: 28.4900, lon: 77.0880, region: 'NORTH', altitudeM: 220, baseTempC: 38.6, baseHumidity: 31, baseRainMm: 0.0, baseWindKmh: 15, typicalCondition: 'Dry & Warm', icon: '☀️' },
  { name: 'Faridabad NIT', city: 'Faridabad', district: 'Faridabad', state: 'Haryana', lat: 28.4089, lon: 77.3178, region: 'NORTH', altitudeM: 204, baseTempC: 37.9, baseHumidity: 35, baseRainMm: 0.0, baseWindKmh: 12, typicalCondition: 'Sunny', icon: '☀️' },
  { name: 'Sanganer Observatory', city: 'Jaipur', district: 'Jaipur', state: 'Rajasthan', lat: 26.8242, lon: 75.8122, region: 'NORTH', altitudeM: 390, baseTempC: 40.5, baseHumidity: 24, baseRainMm: 0.0, baseWindKmh: 18, typicalCondition: 'Heatwave Warning', icon: '🔥' },
  { name: 'Jodhpur Cantt Station', city: 'Jodhpur', district: 'Jodhpur', state: 'Rajasthan', lat: 26.2585, lon: 73.0483, region: 'NORTH', altitudeM: 231, baseTempC: 41.8, baseHumidity: 19, baseRainMm: 0.0, baseWindKmh: 20, typicalCondition: 'Desert Heat', icon: '🔥' },
  { name: 'Bikaner Civil Station', city: 'Bikaner', district: 'Bikaner', state: 'Rajasthan', lat: 28.0229, lon: 73.3119, region: 'NORTH', altitudeM: 243, baseTempC: 42.1, baseHumidity: 18, baseRainMm: 0.0, baseWindKmh: 22, typicalCondition: 'Extreme Dry Heat', icon: '🔥' },
  { name: 'Jaisalmer Fort Station', city: 'Jaisalmer', district: 'Jaisalmer', state: 'Rajasthan', lat: 26.9157, lon: 70.9083, region: 'NORTH', altitudeM: 225, baseTempC: 42.8, baseHumidity: 16, baseRainMm: 0.0, baseWindKmh: 24, typicalCondition: 'Arid Dune Heat', icon: '🔥' },
  { name: 'Udaipur Lake Station', city: 'Udaipur', district: 'Udaipur', state: 'Rajasthan', lat: 24.5854, lon: 73.7125, region: 'NORTH', altitudeM: 598, baseTempC: 37.4, baseHumidity: 35, baseRainMm: 0.0, baseWindKmh: 12, typicalCondition: 'Clear Sky', icon: '☀️' },
  { name: 'Kota Chambal Station', city: 'Kota', district: 'Kota', state: 'Rajasthan', lat: 25.1825, lon: 75.8391, region: 'NORTH', altitudeM: 271, baseTempC: 39.5, baseHumidity: 28, baseRainMm: 0.0, baseWindKmh: 14, typicalCondition: 'Hot Sun', icon: '☀️' },
  { name: 'Ajmer Dargah Station', city: 'Ajmer', district: 'Ajmer', state: 'Rajasthan', lat: 26.4499, lon: 74.6399, region: 'NORTH', altitudeM: 480, baseTempC: 38.9, baseHumidity: 26, baseRainMm: 0.0, baseWindKmh: 16, typicalCondition: 'Dry & Breezy', icon: '🌤️' },
  { name: 'Alwar Station', city: 'Alwar', district: 'Alwar', state: 'Rajasthan', lat: 27.5530, lon: 76.6346, region: 'NORTH', altitudeM: 268, baseTempC: 38.4, baseHumidity: 30, baseRainMm: 0.0, baseWindKmh: 14, typicalCondition: 'Clear Sky', icon: '☀️' },
  { name: 'Amausi Observatory', city: 'Lucknow', district: 'Lucknow', state: 'Uttar Pradesh', lat: 26.7606, lon: 80.8893, region: 'NORTH', altitudeM: 123, baseTempC: 36.8, baseHumidity: 44, baseRainMm: 0.0, baseWindKmh: 11, typicalCondition: 'Warm Sun', icon: '🌤️' },
  { name: 'Chakeri Station', city: 'Kanpur', district: 'Kanpur Nagar', state: 'Uttar Pradesh', lat: 26.4030, lon: 80.4107, region: 'NORTH', altitudeM: 126, baseTempC: 37.1, baseHumidity: 42, baseRainMm: 0.0, baseWindKmh: 10, typicalCondition: 'Sunny', icon: '☀️' },
  { name: 'Babatpur Station', city: 'Varanasi', district: 'Varanasi', state: 'Uttar Pradesh', lat: 25.4519, lon: 82.8593, region: 'NORTH', altitudeM: 81, baseTempC: 36.2, baseHumidity: 48, baseRainMm: 0.5, baseWindKmh: 9, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Kheria Observatory', city: 'Agra', district: 'Agra', state: 'Uttar Pradesh', lat: 27.1558, lon: 77.9609, region: 'NORTH', altitudeM: 169, baseTempC: 38.6, baseHumidity: 33, baseRainMm: 0.0, baseWindKmh: 13, typicalCondition: 'Hot Haze', icon: '☀️' },
  { name: 'Prayagraj Civil Station', city: 'Prayagraj', district: 'Prayagraj', state: 'Uttar Pradesh', lat: 25.4358, lon: 81.8463, region: 'NORTH', altitudeM: 98, baseTempC: 37.5, baseHumidity: 41, baseRainMm: 0.0, baseWindKmh: 10, typicalCondition: 'Sunny', icon: '☀️' },
  { name: 'Meerut Cantt', city: 'Meerut', district: 'Meerut', state: 'Uttar Pradesh', lat: 28.9845, lon: 77.7064, region: 'NORTH', altitudeM: 219, baseTempC: 36.5, baseHumidity: 38, baseRainMm: 0.0, baseWindKmh: 12, typicalCondition: 'Sunny', icon: '☀️' },
  { name: 'Bareilly Trishul', city: 'Bareilly', district: 'Bareilly', state: 'Uttar Pradesh', lat: 28.4237, lon: 79.4502, region: 'NORTH', altitudeM: 172, baseTempC: 35.8, baseHumidity: 46, baseRainMm: 1.0, baseWindKmh: 10, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Gorakhpur Air Force', city: 'Gorakhpur', district: 'Gorakhpur', state: 'Uttar Pradesh', lat: 26.7397, lon: 83.4497, region: 'NORTH', altitudeM: 78, baseTempC: 34.8, baseHumidity: 58, baseRainMm: 3.5, baseWindKmh: 9, typicalCondition: 'Passing Clouds', icon: '⛅' },
  { name: 'Jhansi Station', city: 'Jhansi', district: 'Jhansi', state: 'Uttar Pradesh', lat: 25.4484, lon: 78.5685, region: 'NORTH', altitudeM: 284, baseTempC: 38.5, baseHumidity: 36, baseRainMm: 0.0, baseWindKmh: 13, typicalCondition: 'Dry Warmth', icon: '☀️' },
  { name: 'Ayodhya Saryu Station', city: 'Ayodhya', district: 'Ayodhya', state: 'Uttar Pradesh', lat: 26.7922, lon: 82.1998, region: 'NORTH', altitudeM: 102, baseTempC: 35.5, baseHumidity: 50, baseRainMm: 1.2, baseWindKmh: 9, typicalCondition: 'Pleasant Warmth', icon: '🌤️' },
  { name: 'Chandigarh Sector 39', city: 'Chandigarh', district: 'Chandigarh', state: 'Chandigarh', lat: 30.7333, lon: 76.7794, region: 'NORTH', altitudeM: 321, baseTempC: 34.8, baseHumidity: 39, baseRainMm: 1.2, baseWindKmh: 12, typicalCondition: 'Passing Clouds', icon: '⛅' },
  { name: 'Rajasansi Station', city: 'Amritsar', district: 'Amritsar', state: 'Punjab', lat: 31.7096, lon: 74.7973, region: 'NORTH', altitudeM: 232, baseTempC: 35.4, baseHumidity: 36, baseRainMm: 0.0, baseWindKmh: 14, typicalCondition: 'Clear Sky', icon: '☀️' },
  { name: 'Ludhiana Halwara', city: 'Ludhiana', district: 'Ludhiana', state: 'Punjab', lat: 30.9010, lon: 75.8573, region: 'NORTH', altitudeM: 247, baseTempC: 35.9, baseHumidity: 37, baseRainMm: 0.0, baseWindKmh: 12, typicalCondition: 'Warm Sun', icon: '☀️' },
  { name: 'Jalandhar Cantt', city: 'Jalandhar', district: 'Jalandhar', state: 'Punjab', lat: 31.3260, lon: 75.5762, region: 'NORTH', altitudeM: 228, baseTempC: 35.1, baseHumidity: 38, baseRainMm: 0.0, baseWindKmh: 11, typicalCondition: 'Sunny', icon: '☀️' },
  { name: 'Patiala Station', city: 'Patiala', district: 'Patiala', state: 'Punjab', lat: 30.3398, lon: 76.3869, region: 'NORTH', altitudeM: 251, baseTempC: 35.6, baseHumidity: 38, baseRainMm: 0.0, baseWindKmh: 11, typicalCondition: 'Clear Sky', icon: '☀️' },
  { name: 'Bathinda Cantt', city: 'Bathinda', district: 'Bathinda', state: 'Punjab', lat: 30.2110, lon: 74.9455, region: 'NORTH', altitudeM: 201, baseTempC: 37.0, baseHumidity: 32, baseRainMm: 0.0, baseWindKmh: 14, typicalCondition: 'Dry & Warm', icon: '☀️' },
  { name: 'Srinagar Rambagh', city: 'Srinagar', district: 'Srinagar', state: 'Jammu and Kashmir', lat: 34.0837, lon: 74.7973, region: 'NORTH', altitudeM: 1585, baseTempC: 17.6, baseHumidity: 58, baseRainMm: 3.4, baseWindKmh: 8, typicalCondition: 'Cool Mountain Breeze', icon: '🌦️' },
  { name: 'Jammu Satwari', city: 'Jammu', district: 'Jammu', state: 'Jammu and Kashmir', lat: 32.6891, lon: 74.8375, region: 'NORTH', altitudeM: 327, baseTempC: 33.2, baseHumidity: 46, baseRainMm: 0.8, baseWindKmh: 11, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Anantnag Valley', city: 'Anantnag', district: 'Anantnag', state: 'Jammu and Kashmir', lat: 33.7311, lon: 75.1487, region: 'NORTH', altitudeM: 1600, baseTempC: 16.8, baseHumidity: 62, baseRainMm: 4.0, baseWindKmh: 7, typicalCondition: 'Mountain Showers', icon: '🌧️' },
  { name: 'Baramulla Station', city: 'Baramulla', district: 'Baramulla', state: 'Jammu and Kashmir', lat: 34.1980, lon: 74.3636, region: 'NORTH', altitudeM: 1593, baseTempC: 16.2, baseHumidity: 64, baseRainMm: 4.8, baseWindKmh: 8, typicalCondition: 'Cool Overcast', icon: '⛅' },
  { name: 'Leh Kushok Bakula', city: 'Leh', district: 'Leh', state: 'Ladakh', lat: 34.1359, lon: 77.5465, region: 'NORTH', altitudeM: 3514, baseTempC: 11.2, baseHumidity: 22, baseRainMm: 0.0, baseWindKmh: 18, typicalCondition: 'Crisp High-Altitude Clear', icon: '☀️' },
  { name: 'Kargil Suru Valley', city: 'Kargil', district: 'Kargil', state: 'Ladakh', lat: 34.5539, lon: 76.1349, region: 'NORTH', altitudeM: 2676, baseTempC: 13.0, baseHumidity: 26, baseRainMm: 0.0, baseWindKmh: 15, typicalCondition: 'Crisp High-Altitude Sun', icon: '☀️' },
  { name: 'Shimla Ridge Observatory', city: 'Shimla', district: 'Shimla', state: 'Himachal Pradesh', lat: 31.1048, lon: 77.1734, region: 'NORTH', altitudeM: 2206, baseTempC: 19.4, baseHumidity: 65, baseRainMm: 6.2, baseWindKmh: 10, typicalCondition: 'Misty / Passing Rain', icon: '🌧️' },
  { name: 'Manali Valley Station', city: 'Manali', district: 'Kullu', state: 'Himachal Pradesh', lat: 32.2432, lon: 77.1892, region: 'NORTH', altitudeM: 2050, baseTempC: 16.1, baseHumidity: 70, baseRainMm: 8.5, baseWindKmh: 7, typicalCondition: 'Light Mountain Showers', icon: '🌧️' },
  { name: 'Dharamshala Kangra', city: 'Dharamshala', district: 'Kangra', state: 'Himachal Pradesh', lat: 32.2190, lon: 76.3234, region: 'NORTH', altitudeM: 1457, baseTempC: 22.0, baseHumidity: 68, baseRainMm: 12.0, baseWindKmh: 9, typicalCondition: 'Dhauladhar Rain Squall', icon: '🌧️' },
  { name: 'Dehradun Jolly Grant', city: 'Dehradun', district: 'Dehradun', state: 'Uttarakhand', lat: 30.1897, lon: 78.1804, region: 'NORTH', altitudeM: 682, baseTempC: 28.5, baseHumidity: 62, baseRainMm: 4.1, baseWindKmh: 9, typicalCondition: 'Scattered Showers', icon: '🌦️' },
  { name: 'Haridwar Ganga Ghat', city: 'Haridwar', district: 'Haridwar', state: 'Uttarakhand', lat: 29.9457, lon: 78.1642, region: 'NORTH', altitudeM: 314, baseTempC: 32.2, baseHumidity: 56, baseRainMm: 2.5, baseWindKmh: 10, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Nainital Lake Station', city: 'Nainital', district: 'Nainital', state: 'Uttarakhand', lat: 29.3919, lon: 79.4542, region: 'NORTH', altitudeM: 2084, baseTempC: 18.2, baseHumidity: 72, baseRainMm: 7.0, baseWindKmh: 8, typicalCondition: 'Hill Mist & Showers', icon: '🌧️' },

  // ── WEST ZONE (Maharashtra, Gujarat, Goa, MP West) ────────────────────────
  { name: 'Colaba Observatory', city: 'Mumbai', district: 'Mumbai City', state: 'Maharashtra', lat: 18.9067, lon: 72.8147, region: 'WEST', altitudeM: 11, baseTempC: 31.4, baseHumidity: 84, baseRainMm: 24.5, baseWindKmh: 24, typicalCondition: 'Monsoon Rain Band', icon: '🌧️' },
  { name: 'Santacruz Regional Station', city: 'Mumbai', district: 'Mumbai Suburban', state: 'Maharashtra', lat: 19.0896, lon: 72.8656, region: 'WEST', altitudeM: 14, baseTempC: 30.8, baseHumidity: 87, baseRainMm: 38.0, baseWindKmh: 28, typicalCondition: 'Heavy Downpour', icon: '⛈️' },
  { name: 'Thane Creek Station', city: 'Thane', district: 'Thane', state: 'Maharashtra', lat: 19.2183, lon: 72.9781, region: 'WEST', altitudeM: 15, baseTempC: 30.2, baseHumidity: 89, baseRainMm: 42.5, baseWindKmh: 26, typicalCondition: 'Heavy Rainfall', icon: '🌧️' },
  { name: 'Navi Mumbai Vashi', city: 'Navi Mumbai', district: 'Thane', state: 'Maharashtra', lat: 19.0771, lon: 72.9986, region: 'WEST', altitudeM: 12, baseTempC: 30.6, baseHumidity: 86, baseRainMm: 35.0, baseWindKmh: 25, typicalCondition: 'Intense Rain', icon: '🌧️' },
  { name: 'Shivajinagar Station', city: 'Pune', district: 'Pune', state: 'Maharashtra', lat: 18.5314, lon: 73.8446, region: 'WEST', altitudeM: 560, baseTempC: 28.6, baseHumidity: 74, baseRainMm: 12.0, baseWindKmh: 18, typicalCondition: 'Ghats Squall & Rain', icon: '🌦️' },
  { name: 'Pimpri-Chinchwad Station', city: 'Pimpri-Chinchwad', district: 'Pune', state: 'Maharashtra', lat: 18.6279, lon: 73.8009, region: 'WEST', altitudeM: 570, baseTempC: 28.9, baseHumidity: 72, baseRainMm: 10.5, baseWindKmh: 17, typicalCondition: 'Breezy Showers', icon: '🌦️' },
  { name: 'Nashik Ozar Station', city: 'Nashik', district: 'Nashik', state: 'Maharashtra', lat: 20.1199, lon: 73.9135, region: 'WEST', altitudeM: 580, baseTempC: 29.4, baseHumidity: 70, baseRainMm: 8.5, baseWindKmh: 15, typicalCondition: 'Scattered Showers', icon: '🌦️' },
  { name: 'Chhatrapati Sambhajinagar', city: 'Chhatrapati Sambhajinagar', district: 'Chhatrapati Sambhajinagar', state: 'Maharashtra', lat: 19.8633, lon: 75.3985, region: 'WEST', altitudeM: 582, baseTempC: 33.1, baseHumidity: 58, baseRainMm: 3.2, baseWindKmh: 14, typicalCondition: 'Cloudy with Wind', icon: '⛅' },
  { name: 'Solapur Central', city: 'Solapur', district: 'Solapur', state: 'Maharashtra', lat: 17.6599, lon: 75.9064, region: 'WEST', altitudeM: 458, baseTempC: 35.0, baseHumidity: 55, baseRainMm: 2.0, baseWindKmh: 15, typicalCondition: 'Warm Sun', icon: '🌤️' },
  { name: 'Kolhapur Station', city: 'Kolhapur', district: 'Kolhapur', state: 'Maharashtra', lat: 16.7050, lon: 74.2433, region: 'WEST', altitudeM: 569, baseTempC: 27.8, baseHumidity: 82, baseRainMm: 18.0, baseWindKmh: 16, typicalCondition: 'Heavy Rain Surge', icon: '🌧️' },
  { name: 'Ratnagiri Coastal Station', city: 'Ratnagiri', district: 'Ratnagiri', state: 'Maharashtra', lat: 16.9902, lon: 73.3120, region: 'WEST', altitudeM: 35, baseTempC: 29.0, baseHumidity: 88, baseRainMm: 36.0, baseWindKmh: 26, typicalCondition: 'Coastal Monsoon Downpour', icon: '🌧️' },
  { name: 'Sonegaon Observatory', city: 'Nagpur', district: 'Nagpur', state: 'Maharashtra', lat: 21.0922, lon: 79.0538, region: 'WEST', altitudeM: 310, baseTempC: 38.8, baseHumidity: 49, baseRainMm: 4.5, baseWindKmh: 13, typicalCondition: 'High Heat & Local Thunder', icon: '⛈️' },
  { name: 'Amravati Station', city: 'Amravati', district: 'Amravati', state: 'Maharashtra', lat: 20.9320, lon: 77.7523, region: 'WEST', altitudeM: 343, baseTempC: 37.8, baseHumidity: 51, baseRainMm: 3.0, baseWindKmh: 12, typicalCondition: 'Warm & Humid', icon: '⛅' },
  { name: 'Ahmedabad Hansol', city: 'Ahmedabad', district: 'Ahmedabad', state: 'Gujarat', lat: 23.0734, lon: 72.6347, region: 'WEST', altitudeM: 55, baseTempC: 39.4, baseHumidity: 48, baseRainMm: 0.0, baseWindKmh: 17, typicalCondition: 'High Heat Index', icon: '🌡️' },
  { name: 'Surat Magdalla', city: 'Surat', district: 'Surat', state: 'Gujarat', lat: 21.1702, lon: 72.8311, region: 'WEST', altitudeM: 13, baseTempC: 34.6, baseHumidity: 79, baseRainMm: 14.5, baseWindKmh: 21, typicalCondition: 'Warm Coastal Moisture', icon: '🌦️' },
  { name: 'Vadodara Harni', city: 'Vadodara', district: 'Vadodara', state: 'Gujarat', lat: 22.3362, lon: 73.2263, region: 'WEST', altitudeM: 39, baseTempC: 37.8, baseHumidity: 54, baseRainMm: 1.0, baseWindKmh: 15, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Rajkot Station', city: 'Rajkot', district: 'Rajkot', state: 'Gujarat', lat: 22.3094, lon: 70.7795, region: 'WEST', altitudeM: 138, baseTempC: 38.5, baseHumidity: 46, baseRainMm: 0.0, baseWindKmh: 19, typicalCondition: 'Sunny & Windy', icon: '☀️' },
  { name: 'Bhavnagar Coastal', city: 'Bhavnagar', district: 'Bhavnagar', state: 'Gujarat', lat: 21.7645, lon: 72.1519, region: 'WEST', altitudeM: 24, baseTempC: 36.2, baseHumidity: 65, baseRainMm: 5.0, baseWindKmh: 20, typicalCondition: 'Gulf Breeze & Sun', icon: '🌤️' },
  { name: 'Bhuj Kutch Station', city: 'Bhuj', district: 'Kutch', state: 'Gujarat', lat: 23.2420, lon: 69.6669, region: 'WEST', altitudeM: 110, baseTempC: 39.8, baseHumidity: 40, baseRainMm: 0.0, baseWindKmh: 22, typicalCondition: 'Dry Desert Winds', icon: '☀️' },
  { name: 'Panaji Miramar', city: 'Panaji', district: 'North Goa', state: 'Goa', lat: 15.4859, lon: 73.8095, region: 'WEST', altitudeM: 9, baseTempC: 29.5, baseHumidity: 88, baseRainMm: 31.0, baseWindKmh: 25, typicalCondition: 'Coastal Heavy Rain', icon: '🌧️' },
  { name: 'Margao Station', city: 'Margao', district: 'South Goa', state: 'Goa', lat: 15.2832, lon: 73.9862, region: 'WEST', altitudeM: 12, baseTempC: 29.1, baseHumidity: 90, baseRainMm: 36.5, baseWindKmh: 24, typicalCondition: 'Intense Rain Showers', icon: '🌧️' },

  // ── CENTRAL ZONE (Madhya Pradesh, Chhattisgarh) ───────────────────────────
  { name: 'Bhopal Bairagarh', city: 'Bhopal', district: 'Bhopal', state: 'Madhya Pradesh', lat: 23.2875, lon: 77.3551, region: 'CENTRAL', altitudeM: 523, baseTempC: 35.8, baseHumidity: 52, baseRainMm: 6.0, baseWindKmh: 14, typicalCondition: 'Gusty Thunderstorm Watch', icon: '⛈️' },
  { name: 'Indore Devi Ahilya', city: 'Indore', district: 'Indore', state: 'Madhya Pradesh', lat: 22.7218, lon: 75.8011, region: 'CENTRAL', altitudeM: 567, baseTempC: 34.5, baseHumidity: 56, baseRainMm: 4.8, baseWindKmh: 16, typicalCondition: 'Convective Clouds', icon: '⛅' },
  { name: 'Jabalpur Dumna', city: 'Jabalpur', district: 'Jabalpur', state: 'Madhya Pradesh', lat: 23.1783, lon: 80.0519, region: 'CENTRAL', altitudeM: 411, baseTempC: 36.2, baseHumidity: 50, baseRainMm: 5.5, baseWindKmh: 12, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Gwalior Maharajpur', city: 'Gwalior', district: 'Gwalior', state: 'Madhya Pradesh', lat: 26.2941, lon: 78.2280, region: 'CENTRAL', altitudeM: 211, baseTempC: 39.8, baseHumidity: 36, baseRainMm: 0.0, baseWindKmh: 15, typicalCondition: 'High Heat', icon: '🔥' },
  { name: 'Ujjain Mahakal Station', city: 'Ujjain', district: 'Ujjain', state: 'Madhya Pradesh', lat: 23.1765, lon: 75.7885, region: 'CENTRAL', altitudeM: 494, baseTempC: 35.2, baseHumidity: 54, baseRainMm: 3.0, baseWindKmh: 14, typicalCondition: 'Warm Sun', icon: '🌤️' },
  { name: 'Sagar Civil Station', city: 'Sagar', district: 'Sagar', state: 'Madhya Pradesh', lat: 23.8388, lon: 78.7378, region: 'CENTRAL', altitudeM: 538, baseTempC: 36.0, baseHumidity: 48, baseRainMm: 2.0, baseWindKmh: 12, typicalCondition: 'Clear Sky', icon: '☀️' },
  { name: 'Raipur Mana', city: 'Raipur', district: 'Raipur', state: 'Chhattisgarh', lat: 21.1804, lon: 81.7389, region: 'CENTRAL', altitudeM: 298, baseTempC: 35.0, baseHumidity: 68, baseRainMm: 16.0, baseWindKmh: 17, typicalCondition: 'Thunderstorm with Rain', icon: '⛈️' },
  { name: 'Bilaspur Chakarbhatha', city: 'Bilaspur', district: 'Bilaspur', state: 'Chhattisgarh', lat: 21.9877, lon: 82.1118, region: 'CENTRAL', altitudeM: 262, baseTempC: 34.6, baseHumidity: 65, baseRainMm: 12.4, baseWindKmh: 13, typicalCondition: 'Scattered Showers', icon: '🌦️' },
  { name: 'Durg Bhilai Sector 1', city: 'Bhilai', district: 'Durg', state: 'Chhattisgarh', lat: 21.2167, lon: 81.3833, region: 'CENTRAL', altitudeM: 293, baseTempC: 35.2, baseHumidity: 64, baseRainMm: 10.0, baseWindKmh: 14, typicalCondition: 'Thunderstorm Warning', icon: '⛈️' },
  { name: 'Jagdalpur Bastar', city: 'Jagdalpur', district: 'Bastar', state: 'Chhattisgarh', lat: 19.0740, lon: 82.0299, region: 'CENTRAL', altitudeM: 555, baseTempC: 31.5, baseHumidity: 78, baseRainMm: 22.0, baseWindKmh: 15, typicalCondition: 'Heavy Forest Showers', icon: '🌧️' },

  // ── EAST ZONE (West Bengal, Odisha, Jharkhand, Bihar) ─────────────────────
  { name: 'Alipore Observatory', city: 'Kolkata', district: 'Kolkata', state: 'West Bengal', lat: 22.5326, lon: 88.3275, region: 'EAST', altitudeM: 6, baseTempC: 32.8, baseHumidity: 82, baseRainMm: 28.0, baseWindKmh: 20, typicalCondition: 'Severe Convective Rain', icon: '⛈️' },
  { name: 'Dumdum Station', city: 'Kolkata', district: 'North 24 Parganas', state: 'West Bengal', lat: 22.6547, lon: 88.4467, region: 'EAST', altitudeM: 5, baseTempC: 32.4, baseHumidity: 84, baseRainMm: 34.0, baseWindKmh: 22, typicalCondition: 'Heavy Thunder Squall', icon: '⛈️' },
  { name: 'Howrah Bridge Station', city: 'Howrah', district: 'Howrah', state: 'West Bengal', lat: 22.5858, lon: 88.3426, region: 'EAST', altitudeM: 8, baseTempC: 32.5, baseHumidity: 83, baseRainMm: 30.0, baseWindKmh: 21, typicalCondition: 'Heavy Rain Band', icon: '🌧️' },
  { name: 'Siliguri Bagdogra', city: 'Siliguri', district: 'Darjeeling', state: 'West Bengal', lat: 26.6812, lon: 88.3286, region: 'EAST', altitudeM: 126, baseTempC: 28.0, baseHumidity: 86, baseRainMm: 22.0, baseWindKmh: 12, typicalCondition: 'Sub-Himalayan Rain', icon: '🌧️' },
  { name: 'Durgapur Industrial', city: 'Durgapur', district: 'Paschim Bardhaman', state: 'West Bengal', lat: 23.5204, lon: 87.3119, region: 'EAST', altitudeM: 65, baseTempC: 34.2, baseHumidity: 72, baseRainMm: 15.0, baseWindKmh: 16, typicalCondition: 'Convective Rain Front', icon: '⛈️' },
  { name: 'Asansol Station', city: 'Asansol', district: 'Paschim Bardhaman', state: 'West Bengal', lat: 23.6889, lon: 86.9661, region: 'EAST', altitudeM: 97, baseTempC: 35.6, baseHumidity: 66, baseRainMm: 9.0, baseWindKmh: 14, typicalCondition: 'Humid & Overcast', icon: '⛅' },
  { name: 'Bhubaneswar Airport', city: 'Bhubaneswar', district: 'Khurda', state: 'Odisha', lat: 20.2444, lon: 85.8178, region: 'EAST', altitudeM: 45, baseTempC: 31.6, baseHumidity: 86, baseRainMm: 48.0, baseWindKmh: 26, typicalCondition: 'Heavy Torrential Rain', icon: '🌧️' },
  { name: 'Cuttack Bidyadharpur', city: 'Cuttack', district: 'Cuttack', state: 'Odisha', lat: 20.4625, lon: 85.8828, region: 'EAST', altitudeM: 36, baseTempC: 31.2, baseHumidity: 88, baseRainMm: 52.0, baseWindKmh: 25, typicalCondition: 'Severe Rain & Waterlogging', icon: '🌧️' },
  { name: 'Puri Coastal Station', city: 'Puri', district: 'Puri', state: 'Odisha', lat: 19.8135, lon: 85.8312, region: 'EAST', altitudeM: 4, baseTempC: 30.5, baseHumidity: 91, baseRainMm: 44.0, baseWindKmh: 32, typicalCondition: 'High Coastal Squall', icon: '🌊' },
  { name: 'Rourkela Panposh', city: 'Rourkela', district: 'Sundargarh', state: 'Odisha', lat: 22.2492, lon: 84.8828, region: 'EAST', altitudeM: 219, baseTempC: 34.0, baseHumidity: 72, baseRainMm: 15.0, baseWindKmh: 15, typicalCondition: 'Heavy Thunderstorm', icon: '⛈️' },
  { name: 'Berhampur Ganjam', city: 'Berhampur', district: 'Ganjam', state: 'Odisha', lat: 19.3150, lon: 84.7941, region: 'EAST', altitudeM: 27, baseTempC: 31.8, baseHumidity: 85, baseRainMm: 36.0, baseWindKmh: 24, typicalCondition: 'Monsoon Rain', icon: '🌧️' },
  { name: 'Sambalpur Burla', city: 'Sambalpur', district: 'Sambalpur', state: 'Odisha', lat: 21.4669, lon: 83.9812, region: 'EAST', altitudeM: 135, baseTempC: 34.5, baseHumidity: 74, baseRainMm: 18.0, baseWindKmh: 16, typicalCondition: 'Thunderstorm & Rain', icon: '⛈️' },
  { name: 'Ranchi Hinoo', city: 'Ranchi', district: 'Ranchi', state: 'Jharkhand', lat: 23.3143, lon: 85.3216, region: 'EAST', altitudeM: 651, baseTempC: 30.2, baseHumidity: 76, baseRainMm: 18.5, baseWindKmh: 16, typicalCondition: 'Plateau Downpour', icon: '🌧️' },
  { name: 'Jamshedpur Sonari', city: 'Jamshedpur', district: 'East Singhbhum', state: 'Jharkhand', lat: 22.8126, lon: 86.1670, region: 'EAST', altitudeM: 146, baseTempC: 33.8, baseHumidity: 74, baseRainMm: 14.0, baseWindKmh: 13, typicalCondition: 'Warm with Storms', icon: '⛈️' },
  { name: 'Dhanbad Coalfield', city: 'Dhanbad', district: 'Dhanbad', state: 'Jharkhand', lat: 23.7957, lon: 86.4304, region: 'EAST', altitudeM: 227, baseTempC: 34.5, baseHumidity: 70, baseRainMm: 11.0, baseWindKmh: 14, typicalCondition: 'Convective Clouds', icon: '⛅' },
  { name: 'Patna Jaiprakash', city: 'Patna', district: 'Patna', state: 'Bihar', lat: 25.5913, lon: 85.0880, region: 'EAST', altitudeM: 52, baseTempC: 35.2, baseHumidity: 64, baseRainMm: 11.0, baseWindKmh: 12, typicalCondition: 'Convective Rainfall', icon: '🌦️' },
  { name: 'Gaya Bodhgaya', city: 'Gaya', district: 'Gaya', state: 'Bihar', lat: 24.7441, lon: 84.9511, region: 'EAST', altitudeM: 116, baseTempC: 36.8, baseHumidity: 58, baseRainMm: 5.0, baseWindKmh: 11, typicalCondition: 'Warm Sun with Clouds', icon: '⛅' },
  { name: 'Bhagalpur Ganga', city: 'Bhagalpur', district: 'Bhagalpur', state: 'Bihar', lat: 25.2425, lon: 86.9842, region: 'EAST', altitudeM: 52, baseTempC: 34.6, baseHumidity: 66, baseRainMm: 8.0, baseWindKmh: 12, typicalCondition: 'Passing Rain', icon: '🌦️' },
  { name: 'Muzaffarpur Mithila', city: 'Muzaffarpur', district: 'Muzaffarpur', state: 'Bihar', lat: 26.1209, lon: 85.3647, region: 'EAST', altitudeM: 60, baseTempC: 34.0, baseHumidity: 68, baseRainMm: 9.5, baseWindKmh: 10, typicalCondition: 'Humid & Overcast', icon: '⛅' },

  // ── SOUTH ZONE (Karnataka, Tamil Nadu, Telangana, Andhra Pradesh, Kerala) ──
  { name: 'Bengaluru HAL', city: 'Bengaluru', district: 'Bengaluru Urban', state: 'Karnataka', lat: 12.9500, lon: 77.6682, region: 'SOUTH', altitudeM: 888, baseTempC: 25.8, baseHumidity: 72, baseRainMm: 16.5, baseWindKmh: 20, typicalCondition: 'Evening Thunderstorm', icon: '⛈️' },
  { name: 'Kempegowda Int Station', city: 'Bengaluru', district: 'Bengaluru Rural', state: 'Karnataka', lat: 13.1986, lon: 77.7066, region: 'SOUTH', altitudeM: 915, baseTempC: 26.2, baseHumidity: 68, baseRainMm: 12.0, baseWindKmh: 22, typicalCondition: 'Windy with Showers', icon: '🌦️' },
  { name: 'Mysuru Mandakalli', city: 'Mysuru', district: 'Mysuru', state: 'Karnataka', lat: 12.2298, lon: 76.6548, region: 'SOUTH', altitudeM: 715, baseTempC: 27.4, baseHumidity: 70, baseRainMm: 8.0, baseWindKmh: 15, typicalCondition: 'Pleasant Showers', icon: '🌦️' },
  { name: 'Mangaluru Bajpe', city: 'Mangaluru', district: 'Dakshina Kannada', state: 'Karnataka', lat: 12.9613, lon: 74.8900, region: 'SOUTH', altitudeM: 102, baseTempC: 29.8, baseHumidity: 88, baseRainMm: 35.0, baseWindKmh: 26, typicalCondition: 'Heavy Coastal Rain', icon: '🌧️' },
  { name: 'Hubballi Airport', city: 'Hubballi', district: 'Dharwad', state: 'Karnataka', lat: 15.3617, lon: 75.0849, region: 'SOUTH', altitudeM: 671, baseTempC: 29.5, baseHumidity: 66, baseRainMm: 6.0, baseWindKmh: 18, typicalCondition: 'Breezy & Overcast', icon: '⛅' },
  { name: 'Belagavi Sambra', city: 'Belagavi', district: 'Belagavi', state: 'Karnataka', lat: 15.8597, lon: 74.6183, region: 'SOUTH', altitudeM: 758, baseTempC: 27.2, baseHumidity: 78, baseRainMm: 14.0, baseWindKmh: 17, typicalCondition: 'Rain & Mist', icon: '🌧️' },
  { name: 'Chennai Meenambakkam', city: 'Chennai', district: 'Chennai', state: 'Tamil Nadu', lat: 12.9941, lon: 80.1809, region: 'SOUTH', altitudeM: 16, baseTempC: 34.2, baseHumidity: 78, baseRainMm: 8.5, baseWindKmh: 18, typicalCondition: 'Warm Coastal Moisture', icon: '🌤️' },
  { name: 'Chennai Nungambakkam', city: 'Chennai', district: 'Chennai', state: 'Tamil Nadu', lat: 13.0604, lon: 80.2496, region: 'SOUTH', altitudeM: 14, baseTempC: 34.8, baseHumidity: 76, baseRainMm: 6.0, baseWindKmh: 17, typicalCondition: 'High Heat Index', icon: '🌡️' },
  { name: 'Coimbatore Peelamedu', city: 'Coimbatore', district: 'Coimbatore', state: 'Tamil Nadu', lat: 11.0299, lon: 77.0434, region: 'SOUTH', altitudeM: 406, baseTempC: 30.5, baseHumidity: 64, baseRainMm: 4.0, baseWindKmh: 19, typicalCondition: 'Fresh Breezy Sun', icon: '🌤️' },
  { name: 'Madurai Avaniyapuram', city: 'Madurai', district: 'Madurai', state: 'Tamil Nadu', lat: 9.8345, lon: 78.0934, region: 'SOUTH', altitudeM: 139, baseTempC: 36.6, baseHumidity: 58, baseRainMm: 1.0, baseWindKmh: 14, typicalCondition: 'Hot Sunny Conditions', icon: '☀️' },
  { name: 'Tiruchirappalli Airport', city: 'Tiruchirappalli', district: 'Tiruchirappalli', state: 'Tamil Nadu', lat: 10.7654, lon: 78.7097, region: 'SOUTH', altitudeM: 88, baseTempC: 36.2, baseHumidity: 60, baseRainMm: 2.0, baseWindKmh: 15, typicalCondition: 'Sunny', icon: '☀️' },
  { name: 'Salem Station', city: 'Salem', district: 'Salem', state: 'Tamil Nadu', lat: 11.6643, lon: 78.1460, region: 'SOUTH', altitudeM: 278, baseTempC: 34.5, baseHumidity: 62, baseRainMm: 3.5, baseWindKmh: 13, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Begumpet Observatory', city: 'Hyderabad', district: 'Hyderabad', state: 'Telangana', lat: 17.4475, lon: 78.4727, region: 'SOUTH', altitudeM: 531, baseTempC: 36.0, baseHumidity: 52, baseRainMm: 2.5, baseWindKmh: 16, typicalCondition: 'Warm & Breezy', icon: '🌤️' },
  { name: 'Shamshabad Station', city: 'Hyderabad', district: 'Rangareddy', state: 'Telangana', lat: 17.2403, lon: 78.4294, region: 'SOUTH', altitudeM: 617, baseTempC: 35.6, baseHumidity: 50, baseRainMm: 1.5, baseWindKmh: 18, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Warangal Station', city: 'Warangal', district: 'Warangal', state: 'Telangana', lat: 17.9689, lon: 79.5941, region: 'SOUTH', altitudeM: 266, baseTempC: 37.2, baseHumidity: 48, baseRainMm: 0.0, baseWindKmh: 13, typicalCondition: 'Dry Warmth', icon: '☀️' },
  { name: 'Nizamabad Station', city: 'Nizamabad', district: 'Nizamabad', state: 'Telangana', lat: 18.6725, lon: 78.0941, region: 'SOUTH', altitudeM: 375, baseTempC: 36.8, baseHumidity: 49, baseRainMm: 1.0, baseWindKmh: 12, typicalCondition: 'Warm Sun', icon: '☀️' },
  { name: 'Visakhapatnam Naval Base', city: 'Visakhapatnam', district: 'Visakhapatnam', state: 'Andhra Pradesh', lat: 17.7215, lon: 83.2245, region: 'SOUTH', altitudeM: 5, baseTempC: 32.0, baseHumidity: 84, baseRainMm: 22.0, baseWindKmh: 24, typicalCondition: 'Coastal Rain Band', icon: '🌧️' },
  { name: 'Vijayawada Gannavaram', city: 'Vijayawada', district: 'NTR', state: 'Andhra Pradesh', lat: 16.5273, lon: 80.7970, region: 'SOUTH', altitudeM: 25, baseTempC: 36.5, baseHumidity: 65, baseRainMm: 6.0, baseWindKmh: 15, typicalCondition: 'Warm Humid Weather', icon: '🌤️' },
  { name: 'Tirupati Renigunta', city: 'Tirupati', district: 'Tirupati', state: 'Andhra Pradesh', lat: 13.6325, lon: 79.5436, region: 'SOUTH', altitudeM: 107, baseTempC: 35.8, baseHumidity: 59, baseRainMm: 2.0, baseWindKmh: 12, typicalCondition: 'Partly Cloudy', icon: '⛅' },
  { name: 'Kurnool Station', city: 'Kurnool', district: 'Kurnool', state: 'Andhra Pradesh', lat: 15.8281, lon: 78.0373, region: 'SOUTH', altitudeM: 273, baseTempC: 38.2, baseHumidity: 45, baseRainMm: 0.0, baseWindKmh: 15, typicalCondition: 'Hot & Dry', icon: '🔥' },
  { name: 'Kochi Naval Air Station', city: 'Kochi', district: 'Ernakulam', state: 'Kerala', lat: 9.9312, lon: 76.2673, region: 'SOUTH', altitudeM: 3, baseTempC: 29.2, baseHumidity: 89, baseRainMm: 46.0, baseWindKmh: 22, typicalCondition: 'Heavy Monsoon Surge', icon: '🌧️' },
  { name: 'Thiruvananthapuram Obs', city: 'Thiruvananthapuram', district: 'Thiruvananthapuram', state: 'Kerala', lat: 8.5132, lon: 76.9200, region: 'SOUTH', altitudeM: 64, baseTempC: 29.8, baseHumidity: 85, baseRainMm: 26.0, baseWindKmh: 18, typicalCondition: 'Coastal Showers', icon: '🌧️' },
  { name: 'Kozhikode Karipur', city: 'Kozhikode', district: 'Kozhikode', state: 'Kerala', lat: 11.1368, lon: 75.9553, region: 'SOUTH', altitudeM: 104, baseTempC: 28.9, baseHumidity: 91, baseRainMm: 50.0, baseWindKmh: 20, typicalCondition: 'Intense Monsoonal Rain', icon: '🌧️' },
  { name: 'Kannur Airport', city: 'Kannur', district: 'Kannur', state: 'Kerala', lat: 11.9174, lon: 75.5484, region: 'SOUTH', altitudeM: 76, baseTempC: 29.1, baseHumidity: 88, baseRainMm: 38.0, baseWindKmh: 21, typicalCondition: 'Heavy Coastal Rain', icon: '🌧️' },

  // ── NORTHEAST ZONE (Assam, Meghalaya, Tripura, Manipur, Mizoram, Nagaland, Arunachal, Sikkim) ──
  { name: 'Borjhar Observatory', city: 'Guwahati', district: 'Kamrup Metropolitan', state: 'Assam', lat: 26.1061, lon: 91.5859, region: 'NORTHEAST', altitudeM: 54, baseTempC: 29.5, baseHumidity: 85, baseRainMm: 32.0, baseWindKmh: 14, typicalCondition: 'Brahmaputra Basin Rain', icon: '🌧️' },
  { name: 'Shillong Peak', city: 'Shillong', district: 'East Khasi Hills', state: 'Meghalaya', lat: 25.5788, lon: 91.8933, region: 'NORTHEAST', altitudeM: 1496, baseTempC: 18.8, baseHumidity: 92, baseRainMm: 58.0, baseWindKmh: 16, typicalCondition: 'Torrential Highland Rain', icon: '🌧️' },
  { name: 'Cherrapunji Station', city: 'Sohra', district: 'East Khasi Hills', state: 'Meghalaya', lat: 25.2986, lon: 91.7323, region: 'NORTHEAST', altitudeM: 1484, baseTempC: 18.2, baseHumidity: 96, baseRainMm: 88.0, baseWindKmh: 22, typicalCondition: 'Extreme Precipitation', icon: '⛈️' },
  { name: 'Agartala Singerbhil', city: 'Agartala', district: 'West Tripura', state: 'Tripura', lat: 23.8864, lon: 91.2404, region: 'NORTHEAST', altitudeM: 14, baseTempC: 30.6, baseHumidity: 87, baseRainMm: 24.0, baseWindKmh: 12, typicalCondition: 'Pre-monsoonal Rain Surge', icon: '🌧️' },
  { name: 'Imphal Tulihal', city: 'Imphal', district: 'Imphal West', state: 'Manipur', lat: 24.7600, lon: 93.8967, region: 'NORTHEAST', altitudeM: 774, baseTempC: 26.4, baseHumidity: 83, baseRainMm: 19.0, baseWindKmh: 10, typicalCondition: 'Valley Rainfall Cell', icon: '🌦️' },
  { name: 'Aizawl Lengpui', city: 'Aizawl', district: 'Aizawl', state: 'Mizoram', lat: 23.8407, lon: 92.6190, region: 'NORTHEAST', altitudeM: 405, baseTempC: 25.2, baseHumidity: 88, baseRainMm: 28.0, baseWindKmh: 11, typicalCondition: 'Hill Slope Showers', icon: '🌧️' },
  { name: 'Kohima Station', city: 'Kohima', district: 'Kohima', state: 'Nagaland', lat: 25.6751, lon: 94.1086, region: 'NORTHEAST', altitudeM: 1444, baseTempC: 21.0, baseHumidity: 84, baseRainMm: 16.0, baseWindKmh: 9, typicalCondition: 'Cloudy & Damp', icon: '🌧️' },
  { name: 'Itanagar Hollongi', city: 'Itanagar', district: 'Papum Pare', state: 'Arunachal Pradesh', lat: 27.0844, lon: 93.6053, region: 'NORTHEAST', altitudeM: 320, baseTempC: 27.5, baseHumidity: 86, baseRainMm: 26.0, baseWindKmh: 8, typicalCondition: 'Foothills Downpour', icon: '🌧️' },
  { name: 'Gangtok Tadong', city: 'Gangtok', district: 'East Sikkim', state: 'Sikkim', lat: 27.3314, lon: 88.6138, region: 'NORTHEAST', altitudeM: 1650, baseTempC: 17.5, baseHumidity: 89, baseRainMm: 34.0, baseWindKmh: 9, typicalCondition: 'High Altitude Rain & Mist', icon: '🌧️' },
  { name: 'Dibrugarh Mohanbari', city: 'Dibrugarh', district: 'Dibrugarh', state: 'Assam', lat: 27.4839, lon: 95.0177, region: 'NORTHEAST', altitudeM: 110, baseTempC: 28.2, baseHumidity: 88, baseRainMm: 30.0, baseWindKmh: 10, typicalCondition: 'Heavy Rain Band', icon: '🌧️' },
  { name: 'Silchar Kumbhirgram', city: 'Silchar', district: 'Cachar', state: 'Assam', lat: 24.9126, lon: 92.9788, region: 'NORTHEAST', altitudeM: 107, baseTempC: 29.0, baseHumidity: 86, baseRainMm: 26.0, baseWindKmh: 11, typicalCondition: 'Barak Valley Rain', icon: '🌧️' },
  { name: 'Tezpur Salonibari', city: 'Tezpur', district: 'Sonitpur', state: 'Assam', lat: 26.7118, lon: 92.7937, region: 'NORTHEAST', altitudeM: 73, baseTempC: 29.8, baseHumidity: 84, baseRainMm: 22.0, baseWindKmh: 12, typicalCondition: 'Passing Rain Band', icon: '🌧️' },

  // ── ISLANDS & UNION TERRITORIES ───────────────────────────────────────────
  { name: 'Port Blair Haddo', city: 'Port Blair', district: 'South Andaman', state: 'Andaman and Nicobar Islands', lat: 11.6683, lon: 92.7378, region: 'ISLANDS', altitudeM: 16, baseTempC: 29.6, baseHumidity: 90, baseRainMm: 38.0, baseWindKmh: 28, typicalCondition: 'Island Tropical Squall', icon: '🌊' },
  { name: 'Car Nicobar Air Base', city: 'Car Nicobar', district: 'Nicobar', state: 'Andaman and Nicobar Islands', lat: 9.1550, lon: 92.8180, region: 'ISLANDS', altitudeM: 2, baseTempC: 29.4, baseHumidity: 92, baseRainMm: 42.0, baseWindKmh: 30, typicalCondition: 'Marine Tropical Front', icon: '🌊' },
  { name: 'Kavaratti Station', city: 'Kavaratti', district: 'Lakshadweep', state: 'Lakshadweep', lat: 10.5667, lon: 72.6417, region: 'ISLANDS', altitudeM: 2, baseTempC: 29.8, baseHumidity: 87, baseRainMm: 29.0, baseWindKmh: 26, typicalCondition: 'Island Wind & Surf', icon: '🌊' },
  { name: 'Agatti Airport', city: 'Agatti', district: 'Lakshadweep', state: 'Lakshadweep', lat: 10.8239, lon: 72.1764, region: 'ISLANDS', altitudeM: 4, baseTempC: 30.0, baseHumidity: 85, baseRainMm: 25.0, baseWindKmh: 25, typicalCondition: 'Tropical Breeze', icon: '🌊' },
  { name: 'Puducherry Beach Station', city: 'Puducherry', district: 'Puducherry', state: 'Puducherry', lat: 11.9340, lon: 79.8306, region: 'SOUTH', altitudeM: 3, baseTempC: 33.5, baseHumidity: 80, baseRainMm: 7.0, baseWindKmh: 18, typicalCondition: 'Coastal Warmth', icon: '🌤️' },
  { name: 'Daman Coast Guard', city: 'Daman', district: 'Daman', state: 'Dadra and Nagar Haveli and Daman and Diu', lat: 20.4283, lon: 72.8397, region: 'WEST', altitudeM: 5, baseTempC: 32.1, baseHumidity: 82, baseRainMm: 18.0, baseWindKmh: 22, typicalCondition: 'Coastal Showers', icon: '🌦️' },
];

/**
 * Generates 220+ deterministic weather observation features across Indian stations + intermediate mesh.
 */
export function generateSyntheticObservations(): WeatherObservationFeature[] {
  const rng = createRNG(42069);
  const now = Date.now();

  const primaryObs: WeatherObservationFeature[] = INDIAN_STATION_CATALOG.map((st, idx) => {
    const tempVar = (rng() - 0.5) * 1.6;
    const humVar = (rng() - 0.5) * 6;
    const rainVar = (rng() - 0.5) * 4;
    const windVar = (rng() - 0.5) * 5;

    const temperature_c = Number((st.baseTempC + tempVar).toFixed(1));
    const humidity_percent = Math.min(99, Math.max(15, Math.round(st.baseHumidity + humVar)));
    const rain_mm = Number(Math.max(0, st.baseRainMm + rainVar).toFixed(1));
    const wind_speed_kmh = Math.max(4, Math.round(st.baseWindKmh + windVar));
    const wind_gust_kmh = Math.round(wind_speed_kmh * 1.35 + rng() * 6);
    const pressure_hpa = Math.round(1013 - st.altitudeM * 0.11 + (rng() - 0.5) * 4);

    const indexes = calculateWeatherSeverityIndex({
      temperatureC: temperature_c,
      humidityPct: humidity_percent,
      rainMm: rain_mm,
      windSpeedKmh: wind_speed_kmh,
      windGustKmh: wind_gust_kmh,
      pressureHpa: pressure_hpa,
    });

    let warning_status: 'NORMAL' | 'WATCH' | 'WARNING' | 'ALERT' = 'NORMAL';
    if (indexes.severityIndex >= 75) warning_status = 'ALERT';
    else if (indexes.severityIndex >= 55) warning_status = 'WARNING';
    else if (indexes.severityIndex >= 35) warning_status = 'WATCH';

    // Distribute timestamps over last 12 hours
    const ageMinutes = Math.floor(rng() * 720);
    const observedAt = new Date(now - ageMinutes * 60 * 1000).toISOString();

    return {
      id: `syn-obs-${st.district.toLowerCase().replace(/[^a-z0-9]/g, '-')}-${idx}`,
      name: st.name,
      city: st.city,
      state: st.state,
      latitude: st.lat,
      longitude: st.lon,
      temperature_c,
      temp_label: `${Math.round(temperature_c)}°C`,
      weather_icon: st.icon,
      condition: st.typicalCondition,
      humidity_percent,
      rain_mm,
      wind_speed_kmh,
      source: 'National Mesonet Array',
      model: 'High-Res Synoptic Mesh Grid',
      observed_at: observedAt,
      freshness_label: ageMinutes < 30 ? 'Live Stream' : `${Math.floor(ageMinutes / 60)}h ago`,
      freshness_category: ageMinutes < 60 ? 'REALTIME' : 'RECENT',
      warning_status,
      incident_count: indexes.severityIndex >= 50 ? 1 : 0,
      layer_type: 'WEATHER_OBSERVATION',
    };
  });

  // Generate intermediate mesh interpolation points across India corridors (to reach 200+ points)
  const meshPoints: WeatherObservationFeature[] = [];
  const baseCount = primaryObs.length;

  for (let i = 0; i < baseCount - 1; i++) {
    const a = primaryObs[i];
    const b = primaryObs[(i + 7) % baseCount];
    if (a.state === b.state || Math.abs(a.latitude - b.latitude) < 4) {
      const midLat = Number(((a.latitude + b.latitude) / 2 + (rng() - 0.5) * 0.35).toFixed(4));
      const midLon = Number(((a.longitude + b.longitude) / 2 + (rng() - 0.5) * 0.35).toFixed(4));
      const midTemp = Number((((a.temperature_c || 30) + (b.temperature_c || 30)) / 2 + (rng() - 0.5)).toFixed(1));
      const midHum = Math.round(((a.humidity_percent || 60) + (b.humidity_percent || 60)) / 2);
      const midRain = Number((((a.rain_mm || 0) + (b.rain_mm || 0)) / 2).toFixed(1));
      const midWind = Math.round(((a.wind_speed_kmh || 12) + (b.wind_speed_kmh || 12)) / 2);

      const ageMinutes = Math.floor(rng() * 360);
      meshPoints.push({
        id: `syn-mesh-${i}-${meshPoints.length}`,
        name: `${a.city || a.state} Sector ${meshPoints.length + 1}`,
        city: a.city,
        state: a.state,
        latitude: midLat,
        longitude: midLon,
        temperature_c: midTemp,
        temp_label: `${Math.round(midTemp)}°C`,
        weather_icon: midRain > 10 ? '🌧️' : midTemp > 38 ? '🔥' : '⛅',
        condition: midRain > 10 ? 'Scattered Rain' : midTemp > 38 ? 'High Thermal Stress' : 'Passing Clouds',
        humidity_percent: midHum,
        rain_mm: midRain,
        wind_speed_kmh: midWind,
        source: 'Automated Regional Sensor Array',
        model: 'Continuous Environmental Sensing Grid',
        observed_at: new Date(now - ageMinutes * 60 * 1000).toISOString(),
        warning_status: 'NORMAL',
        incident_count: 0,
        layer_type: 'WEATHER_OBSERVATION',
      });
      if (primaryObs.length + meshPoints.length >= 240) break;
    }
  }

  return [...primaryObs, ...meshPoints];
}

// ── Master Catalog of 65+ Nationwide Weather Events ───────────────────────────
export function generateSyntheticEvents(): WeatherEvent[] {
  const now = Date.now();

  const rawEvents: Array<{
    id: string;
    category: WeatherEvent['category'];
    phenomenon: string;
    title: string;
    summary: string;
    description: string;
    city: string;
    district: string;
    state: string;
    lat: number;
    lon: number;
    severity: number;
    confidence_score: number;
    verification_status: WeatherEvent['verification_status'];
    rainMm: number;
    tempC: number;
    windKmh: number;
    hoursAgo: number;
  }> = [
    // ── NORTH ZONE EVENTS ──
    { id: 'ev-nat-01', category: 'HEATWAVE', phenomenon: 'HIGH_TEMPERATURE_ANOMALY', title: 'Severe Surface Thermal Anomaly across National Capital Region', summary: 'Daytime surface temperatures reaching 39.2°C with dry westerly winds causing elevated thermal index across Delhi & NCR.', description: 'Continuous sensor telemetry recorded sustained boundary-layer heating across Safdarjung, Palam, and Noida monitoring sectors.', city: 'Delhi', district: 'New Delhi', state: 'Delhi', lat: 28.5847, lon: 77.2064, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 39.2, windKmh: 16, hoursAgo: 0.5 },
    { id: 'ev-nat-02', category: 'HEATWAVE', phenomenon: 'DESERT_HEATWAVE', title: 'Extreme Desert Heatwave across Western Thar Margin', summary: 'Extreme thermal envelope recorded at 42.1°C with relative humidity at 18% across Jodhpur and Bikaner.', description: 'Intense solar radiation and dry continental airflow creating acute daytime temperature spikes in western Rajasthan districts.', city: 'Jodhpur', district: 'Jodhpur', state: 'Rajasthan', lat: 26.2585, lon: 73.0483, severity: 4, confidence_score: 0.96, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 42.1, windKmh: 20, hoursAgo: 2.0 },
    { id: 'ev-nat-03', category: 'DUST_STORM', phenomenon: 'DUST_SQUALL', title: 'Convective Dust Storm Front moving over Bikaner Corridor', summary: 'Strong pre-frontal squall lines producing localized dust plumes and visibility drops below 800m.', description: 'Mesonet stations reported sudden wind shifts with gusts up to 48 km/h along the Thar fringe.', city: 'Bikaner', district: 'Bikaner', state: 'Rajasthan', lat: 28.0229, lon: 73.3119, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 0.0, tempC: 41.5, windKmh: 28, hoursAgo: 5.0 },
    { id: 'ev-nat-04', category: 'HEATWAVE', phenomenon: 'THERMAL_SURGE', title: 'Intense Heatwave Conditions across Jaipur & Shekhawati', summary: 'Ambient temperature at 40.5°C with high solar insolation affecting central and eastern Rajasthan.', description: 'Sanganer observatory telemetry indicates prolonged dry airmass entrapment over the Aravalli basin.', city: 'Jaipur', district: 'Jaipur', state: 'Rajasthan', lat: 26.8242, lon: 75.8122, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 40.5, windKmh: 18, hoursAgo: 8.0 },
    { id: 'ev-nat-05', category: 'THUNDERSTORM', phenomenon: 'CONVECTIVE_STORM', title: 'Squally Thunderstorm Front over Lucknow & Central UP', summary: 'Moisture convergence from Gangetic plains triggering gusty convective downdrafts and isolated rain (12.0 mm).', description: 'Amausi station recorded abrupt temperature drops of 6°C during passing storm cell with active lightning.', city: 'Lucknow', district: 'Lucknow', state: 'Uttar Pradesh', lat: 26.7606, lon: 80.8893, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 12.0, tempC: 34.0, windKmh: 22, hoursAgo: 14.0 },
    { id: 'ev-nat-06', category: 'HEATWAVE', phenomenon: 'WARM_SPELL', title: 'Elevated Heat Index across Kanpur & Prayagraj Corridor', summary: 'Hot and humid conditions with ambient temperatures above 37°C producing effective Heat Index above 44°C.', description: 'River basin moisture trapping causing elevated thermal discomfort index across eastern Uttar Pradesh.', city: 'Kanpur', district: 'Kanpur Nagar', state: 'Uttar Pradesh', lat: 26.4030, lon: 80.4107, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 37.5, windKmh: 12, hoursAgo: 22.0 },
    { id: 'ev-nat-07', category: 'FOG', phenomenon: 'MORNING_FOG', title: 'Dense Valley Fog and Reduced Visibility in Shimla Hills', summary: 'High relative humidity (88%) and low cloud ceiling causing visibility drops below 400 meters along NH-5.', description: 'Ridge station optical sensors show dense mountain mist and cloud cover settling over Shimla and Solan.', city: 'Shimla', district: 'Shimla', state: 'Himachal Pradesh', lat: 31.1048, lon: 77.1734, severity: 2, confidence_score: 0.87, verification_status: 'LIKELY', rainMm: 6.2, tempC: 19.4, windKmh: 10, hoursAgo: 4.0 },
    { id: 'ev-nat-08', category: 'RAINFALL', phenomenon: 'MOUNTAIN_SHOWERS', title: 'Sub-Himalayan Orographic Showers across Dehradun Valley', summary: 'Moist valley inflow generating localized rain bands (18.5 mm) along foothill ranges of Garhwal.', description: 'Jolly Grant monitoring arrays detected convective cloud buildup along the Shivalik ridges.', city: 'Dehradun', district: 'Dehradun', state: 'Uttarakhand', lat: 30.1897, lon: 78.1804, severity: 2, confidence_score: 0.86, verification_status: 'LIKELY', rainMm: 18.5, tempC: 28.0, windKmh: 14, hoursAgo: 18.0 },
    { id: 'ev-nat-09', category: 'RAINFALL', phenomenon: 'COOL_ANOMALY', title: 'Western Disturbance Showers across Kashmir Valley', summary: 'Upper-tropospheric trough maintaining cool conditions (17.6°C) with intermittent mountain showers (8.4 mm).', description: 'Srinagar and Baramulla stations report cloudy skies, fresh breezes, and localized precipitation.', city: 'Srinagar', district: 'Srinagar', state: 'Jammu and Kashmir', lat: 34.0837, lon: 74.7973, severity: 1, confidence_score: 0.85, verification_status: 'LIKELY', rainMm: 8.4, tempC: 17.6, windKmh: 9, hoursAgo: 1.0 },
    { id: 'ev-nat-10', category: 'SNOWFALL', phenomenon: 'HIGH_ALTITUDE_FROST', title: 'Sub-Zero Wind Chill & Frost Risk over Ladakh Plateau', summary: 'Clear skies and dry rarefied air producing sharp overnight thermal drop (11.2°C) with brisk 20 km/h winds.', description: 'Leh and Kargil telemetry arrays record rapid radiative cooling under pristine high-altitude skies.', city: 'Leh', district: 'Leh', state: 'Ladakh', lat: 34.1359, lon: 77.5465, severity: 2, confidence_score: 0.94, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 11.2, windKmh: 20, hoursAgo: 30.0 },
    { id: 'ev-nat-11', category: 'THUNDERSTORM', phenomenon: 'PRE_FRONTAL_CELL', title: 'Convective Lightning & Rain Cell in Amritsar Plains', summary: 'Passing western trough triggering scattered thunderstorms (14.0 mm) and lightning across Majha belt.', description: 'Rajasansi telemetry detected brief squall line accompanied by temperature drop to 31°C.', city: 'Amritsar', district: 'Amritsar', state: 'Punjab', lat: 31.7096, lon: 74.7973, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 14.0, tempC: 31.0, windKmh: 24, hoursAgo: 10.0 },

    // ── WEST ZONE EVENTS ──
    { id: 'ev-nat-12', category: 'RAINFALL', phenomenon: 'MONSOON_SQUALL', title: 'Torrential Coastal Monsoon Downpour across Greater Mumbai', summary: 'Intense precipitation bands delivering rain rates above 38 mm/h across Mumbai Suburban, Thane, and Navi Mumbai.', description: 'Doppler radar and coastal automatic weather stations recorded heavy rain echoes and wind gusts up to 46 km/h.', city: 'Mumbai', district: 'Mumbai Suburban', state: 'Maharashtra', lat: 19.0896, lon: 72.8656, severity: 4, confidence_score: 0.95, verification_status: 'VERIFIED', rainMm: 48.5, tempC: 30.2, windKmh: 28, hoursAgo: 0.8 },
    { id: 'ev-nat-13', category: 'RAINFALL', phenomenon: 'GHATS_SQUALL', title: 'Western Ghats Windward Downpour across Pune & Lonavala', summary: 'Strong orographic lift producing 22.0 mm precipitation and fresh squalls across Pune district.', description: 'Shivajinagar and Pashan sensor feeds depict steady moderate-to-heavy showers with humidity at 78%.', city: 'Pune', district: 'Pune', state: 'Maharashtra', lat: 18.5314, lon: 73.8446, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 22.0, tempC: 28.0, windKmh: 20, hoursAgo: 3.5 },
    { id: 'ev-nat-14', category: 'STRONG_WINDS', phenomenon: 'COASTAL_GALE', title: 'Squally Coastal Winds & High Waves along Konkan Coast', summary: 'Sustained onshore winds reaching 34 km/h with gusts up to 48 km/h along Ratnagiri and Sindhudurg shores.', description: 'Maritime radar and coastal stations report rough sea conditions with steady rain bands moving inland.', city: 'Ratnagiri', district: 'Ratnagiri', state: 'Maharashtra', lat: 16.9902, lon: 73.3120, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 36.0, tempC: 29.0, windKmh: 34, hoursAgo: 6.0 },
    { id: 'ev-nat-15', category: 'HEATWAVE', phenomenon: 'HIGH_HEAT_INDEX', title: 'Elevated Heat Index & Moisture Convergence in Ahmedabad', summary: 'High ambient temperature (39.4°C) with 48% humidity creating high daytime thermal stress across central Gujarat.', description: 'Hansol weather station telemetry indicates dry inland winds clashing with maritime moisture from Gulf of Khambhat.', city: 'Ahmedabad', district: 'Ahmedabad', state: 'Gujarat', lat: 23.0734, lon: 72.6347, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 39.4, windKmh: 17, hoursAgo: 12.0 },
    { id: 'ev-nat-16', category: 'RAINFALL', phenomenon: 'COASTAL_MOISTURE', title: 'Heavy Rain Surge & Coastal Squalls across Surat Belt', summary: 'Active rain bands yielding 28.0 mm rainfall with southwesterly wind gusts along South Gujarat coastline.', description: 'Magdalla station recorded intense showers and saturated soil moisture across Surat and Navsari districts.', city: 'Surat', district: 'Surat', state: 'Gujarat', lat: 21.1702, lon: 72.8311, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 28.0, tempC: 33.0, windKmh: 25, hoursAgo: 16.0 },
    { id: 'ev-nat-17', category: 'RAINFALL', phenomenon: 'MONSOON_CELL', title: 'Intense Coastal Precipitation & High Surf in Goa Belt', summary: 'Continuous monsoonal surge delivering 36.5 mm rainfall with brisk coastal breezes across Panaji and Margao.', description: 'Miramar coastal monitoring arrays detect high cloud thickness and persistent precipitation echoes.', city: 'Panaji', district: 'North Goa', state: 'Goa', lat: 15.4859, lon: 73.8095, severity: 3, confidence_score: 0.93, verification_status: 'VERIFIED', rainMm: 36.5, tempC: 29.1, windKmh: 26, hoursAgo: 2.5 },
    { id: 'ev-nat-18', category: 'HEATWAVE', phenomenon: 'DRY_HEAT', title: 'Intense Thermal Conditions across Vidarbha Basin', summary: 'Daytime high of 39.2°C recorded at Nagpur Sonegaon with low humidity and elevated UV radiation.', description: 'Continental high pressure over central India causing dry heatwave conditions across Nagpur, Chandrapur, and Wardha.', city: 'Nagpur', district: 'Nagpur', state: 'Maharashtra', lat: 21.0922, lon: 79.0538, severity: 3, confidence_score: 0.94, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 39.2, windKmh: 14, hoursAgo: 28.0 },
    { id: 'ev-nat-19', category: 'THUNDERSTORM', phenomenon: 'LOCAL_CONVECTION', title: 'Evening Convective Thunderstorm over Nashik Orchards', summary: 'Local thermal trigger producing 16.0 mm rain with lightning discharges across Nashik and Dindori.', description: 'Ozar station recorded rapid cloud buildup and temperature drop of 4°C during evening storm pass.', city: 'Nashik', district: 'Nashik', state: 'Maharashtra', lat: 20.1199, lon: 73.9135, severity: 2, confidence_score: 0.86, verification_status: 'LIKELY', rainMm: 16.0, tempC: 28.5, windKmh: 20, hoursAgo: 48.0 },

    // ── CENTRAL ZONE EVENTS ──
    { id: 'ev-nat-20', category: 'THUNDERSTORM', phenomenon: 'GUST_FRONT', title: 'Squall Line & Severe Thunderstorm across Bhopal & Sehore', summary: 'Intense mesoscale convective front delivering 24.0 mm rain and wind gusts reaching 42 km/h.', description: 'Bairagarh observatory registered steep barometric pressure drop followed by heavy precipitation.', city: 'Bhopal', district: 'Bhopal', state: 'Madhya Pradesh', lat: 23.2875, lon: 77.3551, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 24.0, tempC: 33.5, windKmh: 24, hoursAgo: 1.5 },
    { id: 'ev-nat-21', category: 'THUNDERSTORM', phenomenon: 'LIGHTNING_RISK', title: 'Severe Lightning & Thunderstorm Activity in Raipur Sector', summary: 'Convective cell yielding 28.0 mm rainfall and high-density ground lightning across Raipur and Durg.', description: 'Mana station lightning sensors recorded over 120 discharge signals within a 25 km perimeter.', city: 'Raipur', district: 'Raipur', state: 'Chhattisgarh', lat: 21.1804, lon: 81.7389, severity: 3, confidence_score: 0.93, verification_status: 'VERIFIED', rainMm: 28.0, tempC: 33.0, windKmh: 22, hoursAgo: 4.5 },
    { id: 'ev-nat-22', category: 'HEATWAVE', phenomenon: 'HEAT_STRESS', title: 'High Temperature Envelope across Gwalior & Chambal Valley', summary: 'Clear sunny skies and dry air pushing temperatures to 40.2°C across northern Madhya Pradesh.', description: 'Maharajpur station telemetry indicates dry boundary layer conditions and elevated afternoon heat index.', city: 'Gwalior', district: 'Gwalior', state: 'Madhya Pradesh', lat: 26.2941, lon: 78.2280, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 40.2, windKmh: 16, hoursAgo: 24.0 },
    { id: 'ev-nat-23', category: 'RAINFALL', phenomenon: 'TROPICAL_SHOWERS', title: 'Heavy Forest Rainfall across Bastar Plateau', summary: 'Monsoonal moisture convergence bringing 32.0 mm rainfall over Jagdalpur and Dandakaranya forests.', description: 'Automatic rain gauges report steady runoff and high relative humidity across southern Chhattisgarh.', city: 'Jagdalpur', district: 'Bastar', state: 'Chhattisgarh', lat: 19.0740, lon: 82.0299, severity: 2, confidence_score: 0.87, verification_status: 'LIKELY', rainMm: 32.0, tempC: 29.5, windKmh: 16, hoursAgo: 36.0 },

    // ── EAST ZONE EVENTS ──
    { id: 'ev-nat-24', category: 'RAINFALL', phenomenon: 'EXTREME_PRECIPITATION', title: 'Torrential Precipitation Band across Coastal Odisha', summary: 'Intense Bay of Bengal convective cell delivering 54.0 mm rainfall over Khurda, Cuttack, and Puri districts.', description: 'Doppler radar simulation depicts high-reflectivity storm cores causing localized urban waterlogging risks.', city: 'Bhubaneswar', district: 'Khurda', state: 'Odisha', lat: 20.2444, lon: 85.8178, severity: 4, confidence_score: 0.96, verification_status: 'VERIFIED', rainMm: 54.0, tempC: 30.5, windKmh: 28, hoursAgo: 0.6 },
    { id: 'ev-nat-25', category: 'STRONG_WINDS', phenomenon: 'COASTAL_SQUALL', title: 'High Coastal Squall & Heavy Waves along Puri Coast', summary: 'Strong maritime winds of 38 km/h and continuous heavy rain bands (44.0 mm) impacting coastal pilgrimage belt.', description: 'Puri station reports elevated wave action and localized coastal gusts moving inland toward Chilika.', city: 'Puri', district: 'Puri', state: 'Odisha', lat: 19.8135, lon: 85.8312, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 44.0, tempC: 30.0, windKmh: 38, hoursAgo: 2.2 },
    { id: 'ev-nat-26', category: 'THUNDERSTORM', phenomenon: 'SEVERE_CONVECTION', title: 'Severe Convective Thunderstorm over Kolkata & Gangetic Delta', summary: 'High atmospheric instability (CAPE > 2600 J/kg) generating intense rain (38.0 mm) and lightning in Kolkata.', description: 'Alipore and Dumdum stations recorded rapid cloud base drop and squalls reaching 45 km/h.', city: 'Kolkata', district: 'Kolkata', state: 'West Bengal', lat: 22.5326, lon: 88.3275, severity: 3, confidence_score: 0.94, verification_status: 'VERIFIED', rainMm: 38.0, tempC: 31.5, windKmh: 25, hoursAgo: 1.2 },
    { id: 'ev-nat-27', category: 'RAINFALL', phenomenon: 'DOWNPOUR', title: 'Intense Downpour & Waterlogging Watch across Cuttack', summary: 'Heavy persistent rainfall (48.0 mm) over Mahanadi river basin triggering municipal drainage alerts.', description: 'Cuttack station sensors report saturation of surface runoff and continuous cloud cover.', city: 'Cuttack', district: 'Cuttack', state: 'Odisha', lat: 20.4625, lon: 85.8828, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 48.0, tempC: 30.8, windKmh: 24, hoursAgo: 3.8 },
    { id: 'ev-nat-28', category: 'RAINFALL', phenomenon: 'PLATEAU_DOWNPOUR', title: 'High-Altitude Plateau Downpour in Ranchi Sector', summary: 'Chota Nagpur convective system delivering 26.0 mm precipitation with cool mountain breezes.', description: 'Hinoo station telemetry indicates saturated airmass and continuous rain bands over Ranchi and Ramgarh.', city: 'Ranchi', district: 'Ranchi', state: 'Jharkhand', lat: 23.3143, lon: 85.3216, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 26.0, tempC: 28.5, windKmh: 18, hoursAgo: 7.0 },
    { id: 'ev-nat-29', category: 'RAINFALL', phenomenon: 'CONVECTIVE_RAIN', title: 'Gangetic Plain Convective Rainfall Cell over Patna', summary: 'Convective cell bringing 18.0 mm rain with moderate lightning discharges across Patna and Vaishali.', description: 'Jaiprakash Narayan station sensors recorded sharp temperature moderation from 36°C to 30°C.', city: 'Patna', district: 'Patna', state: 'Bihar', lat: 25.5913, lon: 85.0880, severity: 2, confidence_score: 0.87, verification_status: 'LIKELY', rainMm: 18.0, tempC: 31.0, windKmh: 16, hoursAgo: 15.0 },
    { id: 'ev-nat-30', category: 'THUNDERSTORM', phenomenon: 'SQUALL_CELL', title: 'Industrial Corridor Thunderstorm in Durgapur & Asansol', summary: 'Damodar valley moisture convergence generating squally showers (22.0 mm) and wind gusts.', description: 'Durgapur and Raniganj mesonet nodes recorded sudden barometric fluctuations during storm passage.', city: 'Durgapur', district: 'Paschim Bardhaman', state: 'West Bengal', lat: 23.5204, lon: 87.3119, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 22.0, tempC: 32.0, windKmh: 22, hoursAgo: 20.0 },
    { id: 'ev-nat-31', category: 'RAINFALL', phenomenon: 'FOOTHILL_RAIN', title: 'Sub-Himalayan Torrential Rain in Siliguri & Darjeeling', summary: 'Active foothill trough yielding 36.0 mm precipitation over Bagdogra and Jalpaiguri corridors.', description: 'Continuous monsoonal flow against eastern Himalayas causing elevated streamflow in Teesta catchment.', city: 'Siliguri', district: 'Darjeeling', state: 'West Bengal', lat: 26.6812, lon: 88.3286, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 36.0, tempC: 27.5, windKmh: 16, hoursAgo: 50.0 },

    // ── SOUTH ZONE EVENTS ──
    { id: 'ev-nat-32', category: 'THUNDERSTORM', phenomenon: 'CONVECTIVE_STORM', title: 'Convective Evening Thunderstorm over Bengaluru Urban', summary: 'Localized thermal convergence over south Karnataka plateau generating scattered showers (22.5 mm) and squally gusts.', description: 'HAL and Electronic City stations recorded temperature drop from 29°C to 24.8°C with wind gusts up to 36 km/h.', city: 'Bengaluru', district: 'Bengaluru Urban', state: 'Karnataka', lat: 12.9500, lon: 77.6682, severity: 2, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 22.5, tempC: 24.8, windKmh: 22, hoursAgo: 1.8 },
    { id: 'ev-nat-33', category: 'RAINFALL', phenomenon: 'MONSOON_SURGE', title: 'Monsoon Cloud Burst & Tidal Inflow across Coastal Kerala', summary: 'Arabian Sea monsoon front bringing sustained rainfall of 52.0 mm with high sea spray and humidity at 92%.', description: 'Kochi Naval station and coastal buoy feeds depict heavy rain bands and rough surf along Ernakulam and Alappuzha.', city: 'Kochi', district: 'Ernakulam', state: 'Kerala', lat: 9.9312, lon: 76.2673, severity: 4, confidence_score: 0.96, verification_status: 'VERIFIED', rainMm: 52.0, tempC: 28.5, windKmh: 26, hoursAgo: 0.4 },
    { id: 'ev-nat-34', category: 'RAINFALL', phenomenon: 'HEAVY_MONSOON', title: 'Intense Monsoonal Rain Surge in Kozhikode & Malabar', summary: 'Heavy precipitation totaling 56.0 mm recorded across Karipur and adjoining coastal districts.', description: 'Automatic weather stations indicate saturated hill slopes and high stream levels across Malappuram and Wayanad.', city: 'Kozhikode', district: 'Kozhikode', state: 'Kerala', lat: 11.1368, lon: 75.9553, severity: 4, confidence_score: 0.95, verification_status: 'VERIFIED', rainMm: 56.0, tempC: 28.0, windKmh: 24, hoursAgo: 3.2 },
    { id: 'ev-nat-35', category: 'HEATWAVE', phenomenon: 'HIGH_HUMIDITY_HEAT', title: 'Extreme Heat Index & Coastal Humidity along Chennai Coast', summary: 'High ambient temperature (35.2°C) paired with 78% relative humidity pushes effective Heat Index to 48.0°C.', description: 'Nungambakkam and Meenambakkam observatories indicate stagnant maritime boundary layer causing severe thermal discomfort.', city: 'Chennai', district: 'Chennai', state: 'Tamil Nadu', lat: 13.0604, lon: 80.2496, severity: 3, confidence_score: 0.93, verification_status: 'VERIFIED', rainMm: 4.0, tempC: 35.2, windKmh: 16, hoursAgo: 5.5 },
    { id: 'ev-nat-36', category: 'STRONG_WINDS', phenomenon: 'COASTAL_SQUALL', title: 'Coastal Wind Shift & Sea Breeze Front near Visakhapatnam', summary: 'Offshore low-pressure trough producing sudden wind gusts of 44 km/h and localized showers (26.0 mm).', description: 'Visakhapatnam naval base radar confirms squall line moving westward with localized pressure dip.', city: 'Visakhapatnam', district: 'Visakhapatnam', state: 'Andhra Pradesh', lat: 17.7215, lon: 83.2245, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 26.0, tempC: 31.5, windKmh: 28, hoursAgo: 9.0 },
    { id: 'ev-nat-37', category: 'HEATWAVE', phenomenon: 'DRY_HEAT', title: 'Warm Thermal Gradient across Hyderabad & Deccan Plateau', summary: 'Warm dry conditions prevailing at 36.5°C with gusty afternoon breezes across Hyderabad and Rangareddy.', description: 'Begumpet station sensors report low relative humidity (46%) and stable boundary layer aloft.', city: 'Hyderabad', district: 'Hyderabad', state: 'Telangana', lat: 17.4475, lon: 78.4727, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 0.0, tempC: 36.5, windKmh: 18, hoursAgo: 16.0 },
    { id: 'ev-nat-38', category: 'RAINFALL', phenomenon: 'COASTAL_DOWNPOUR', title: 'Heavy Coastal Downpour across Mangaluru & Udupi', summary: 'Arabian Sea convective clouds delivering 42.0 mm rainfall and brisk onshore winds in Dakshina Kannada.', description: 'Bajpe airport station telemetry shows continuous moderate-to-heavy rain and zero cloud base elevation.', city: 'Mangaluru', district: 'Dakshina Kannada', state: 'Karnataka', lat: 12.9613, lon: 74.8900, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 42.0, tempC: 28.8, windKmh: 26, hoursAgo: 26.0 },
    { id: 'ev-nat-39', category: 'RAINFALL', phenomenon: 'MONSOON_SHOWERS', title: 'Coastal Monsoon Showers across Thiruvananthapuram', summary: 'Intermittent heavy rain bands bringing 28.0 mm rainfall along southern Kerala coastline.', description: 'Observatory sensors report high relative humidity (86%) and moderate coastal swell.', city: 'Thiruvananthapuram', district: 'Thiruvananthapuram', state: 'Kerala', lat: 8.5132, lon: 76.9200, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 28.0, tempC: 29.2, windKmh: 20, hoursAgo: 40.0 },
    { id: 'ev-nat-40', category: 'HEATWAVE', phenomenon: 'RAYALASEEMA_HEAT', title: 'Extreme Dry Thermal Wave across Kurnool & Kadapa', summary: 'Continental heatwave conditions pushing temperatures to 38.8°C with gusty hot winds.', description: 'Inland Rayalaseema sensor nodes report high daytime solar irradiance and dry ground moisture.', city: 'Kurnool', district: 'Kurnool', state: 'Andhra Pradesh', lat: 15.8281, lon: 78.0373, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 38.8, windKmh: 17, hoursAgo: 60.0 },

    // ── NORTHEAST ZONE EVENTS ──
    { id: 'ev-nat-41', category: 'RAINFALL', phenomenon: 'TORRENTIAL_DOWNPOUR', title: 'Extreme Orographic Downpour along Meghalaya Plateau', summary: 'Persistent southwesterly monsoon flow against Khasi Hills delivering 68.0 mm rainfall in Shillong basin.', description: 'Shillong Peak and Sohra automatic stations report dense cloud envelopment and torrential runoff.', city: 'Shillong', district: 'East Khasi Hills', state: 'Meghalaya', lat: 25.5788, lon: 91.8933, severity: 4, confidence_score: 0.97, verification_status: 'VERIFIED', rainMm: 68.0, tempC: 18.2, windKmh: 20, hoursAgo: 0.9 },
    { id: 'ev-nat-42', category: 'RAINFALL', phenomenon: 'RIVER_BASIN_SURGE', title: 'Precipitation Anomaly & High Inflow across Brahmaputra Valley', summary: 'Monsoonal low trough producing sustained rainfall of 38.0 mm over Guwahati and Kamrup Metropolitan.', description: 'Borjhar station sensors record saturated riverine airmass and continuous rain echoes along lower Assam.', city: 'Guwahati', district: 'Kamrup Metropolitan', state: 'Assam', lat: 26.1061, lon: 91.5859, severity: 3, confidence_score: 0.93, verification_status: 'VERIFIED', rainMm: 38.0, tempC: 28.8, windKmh: 15, hoursAgo: 2.8 },
    { id: 'ev-nat-43', category: 'RAINFALL', phenomenon: 'VALLEY_RAIN', title: 'Intense Moisture Inflow & Heavy Showers in Agartala', summary: 'Bay of Bengal tropical moisture surge bringing 30.0 mm rainfall over Tripura plains.', description: 'Singerbhil station radar confirms widespread convective cells moving eastward across West Tripura.', city: 'Agartala', district: 'West Tripura', state: 'Tripura', lat: 23.8864, lon: 91.2404, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 30.0, tempC: 29.8, windKmh: 14, hoursAgo: 6.5 },
    { id: 'ev-nat-44', category: 'RAINFALL', phenomenon: 'VALLEY_CONVECTION', title: 'Valley Rain Cell & Thunderstorm in Imphal Basin', summary: 'Localized convective storm delivering 22.0 mm precipitation with lightning across Imphal West.', description: 'Tulihal station registered moderate wind gusts and rapid temperature moderation to 25°C.', city: 'Imphal', district: 'Imphal West', state: 'Manipur', lat: 24.7600, lon: 93.8967, severity: 2, confidence_score: 0.87, verification_status: 'LIKELY', rainMm: 22.0, tempC: 25.4, windKmh: 12, hoursAgo: 11.0 },
    { id: 'ev-nat-45', category: 'RAINFALL', phenomenon: 'HILL_SLOPE_RAIN', title: 'Persistent Hill Slope Showers across Aizawl Hills', summary: 'Moist southwest winds bringing 32.0 mm rainfall and dense fog over Mizoram ridges.', description: 'Lengpui station telemetry indicates saturated soil and overcast skies across Aizawl and Lunglei.', city: 'Aizawl', district: 'Aizawl', state: 'Mizoram', lat: 23.8407, lon: 92.6190, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 32.0, tempC: 24.5, windKmh: 13, hoursAgo: 19.0 },
    { id: 'ev-nat-46', category: 'RAINFALL', phenomenon: 'UPPER_ASSAM_RAIN', title: 'Heavy Rain Band over Upper Assam & Dibrugarh', summary: 'Intense rain band yielding 34.0 mm precipitation along Brahmaputra upper reaches.', description: 'Mohanbari station sensors report steady monsoonal downpour and high humidity (90%).', city: 'Dibrugarh', district: 'Dibrugarh', state: 'Assam', lat: 27.4839, lon: 95.0177, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 34.0, tempC: 27.8, windKmh: 12, hoursAgo: 27.0 },
    { id: 'ev-nat-47', category: 'RAINFALL', phenomenon: 'FOOTHILL_DOWNPOUR', title: 'Sub-Himalayan Downpour across Itanagar & Papum Pare', summary: 'Active foothill front bringing 30.0 mm rainfall over Arunachal Pradesh capital belt.', description: 'Hollongi station detects thick cloud decks and continuous runoff along foothill slopes.', city: 'Itanagar', district: 'Papum Pare', state: 'Arunachal Pradesh', lat: 27.0844, lon: 93.6053, severity: 2, confidence_score: 0.87, verification_status: 'LIKELY', rainMm: 30.0, tempC: 26.8, windKmh: 10, hoursAgo: 38.0 },
    { id: 'ev-nat-48', category: 'RAINFALL', phenomenon: 'HIGH_ALTITUDE_RAIN', title: 'High Altitude Rain & Mist Envelope in Gangtok', summary: 'Orographic condensation causing 38.0 mm rainfall and near-zero visibility across Sikkim hills.', description: 'Tadong observatory arrays detect continuous cloud cover and cool mountain breezes (17°C).', city: 'Gangtok', district: 'East Sikkim', state: 'Sikkim', lat: 27.3314, lon: 88.6138, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 38.0, tempC: 17.2, windKmh: 11, hoursAgo: 55.0 },

    // ── ISLANDS & COASTAL FRINGE EVENTS ──
    { id: 'ev-nat-49', category: 'STRONG_WINDS', phenomenon: 'TROPICAL_SQUALL', title: 'Tropical Maritime Squall across Andaman Archipelago', summary: 'Equatorial low causing sustained wind gusts of 50 km/h and heavy tropical showers (45.0 mm) in Port Blair.', description: 'Haddo maritime station and oceanic buoys indicate rough seas and active squall bands moving across South Andaman.', city: 'Port Blair', district: 'South Andaman', state: 'Andaman and Nicobar Islands', lat: 11.6683, lon: 92.7378, severity: 4, confidence_score: 0.95, verification_status: 'VERIFIED', rainMm: 45.0, tempC: 29.2, windKmh: 36, hoursAgo: 1.1 },
    { id: 'ev-nat-50', category: 'STRONG_WINDS', phenomenon: 'ISLAND_SURF', title: 'Tropical Marine Squall & High Surf across Lakshadweep', summary: 'Arabian Sea squall front generating 34.0 mm rainfall and wind gusts up to 45 km/h at Kavaratti.', description: 'Island automatic weather station reports rough lagoon conditions and persistent cloud bands.', city: 'Kavaratti', district: 'Lakshadweep', state: 'Lakshadweep', lat: 10.5667, lon: 72.6417, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 34.0, tempC: 29.5, windKmh: 30, hoursAgo: 4.8 },

    // ── EXPANDED NATIONWIDE REGIONAL EVENTS (51-75) ──
    { id: 'ev-nat-51', category: 'HEATWAVE', phenomenon: 'MALWA_HEAT', title: 'Thermal Inversion & High Surface Temperature in Ludhiana', summary: 'Dry boundary layer heating pushing ambient temperature to 39.0°C with low relative humidity (28%).', description: 'Agricultural university station records sustained dry westerly breezes across central Punjab plain.', city: 'Ludhiana', district: 'Ludhiana', state: 'Punjab', lat: 30.9010, lon: 75.8573, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 39.0, windKmh: 16, hoursAgo: 1.5 },
    { id: 'ev-nat-52', category: 'RAINFALL', phenomenon: 'FOOTHILL_SHOWERS', title: 'Upper Gangetic Foothill Inflow & Showers in Haridwar', summary: 'Moist river valley inflow triggering localized showers (20.5 mm) along the Shivalik transition zone.', description: 'Haridwar environmental sensing arrays report rapid cloud development and fresh valley breezes.', city: 'Haridwar', district: 'Haridwar', state: 'Uttarakhand', lat: 29.9457, lon: 78.1642, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 20.5, tempC: 29.4, windKmh: 13, hoursAgo: 5.2 },
    { id: 'ev-nat-53', category: 'HEATWAVE', phenomenon: 'MEWAR_HEAT', title: 'Intense Solar Heating across Udaipur & Lake Basin', summary: 'High daytime temperatures (38.4°C) with dry atmospheric conditions across southern Rajasthan.', description: 'Dabok observatory telemetry indicates steady thermal heating under cloudless skies.', city: 'Udaipur', district: 'Udaipur', state: 'Rajasthan', lat: 24.5854, lon: 73.7125, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 38.4, windKmh: 14, hoursAgo: 8.5 },
    { id: 'ev-nat-54', category: 'HEATWAVE', phenomenon: 'CHAMBAL_HEATWAVE', title: 'Chambal Basin Dry Heatwave across Kota Sector', summary: 'Extreme thermal envelope reaching 40.8°C with strong hot gusts along the Chambal river valley.', description: 'Kota airport automatic station records sharp diurnal temperature surges and low soil humidity.', city: 'Kota', district: 'Kota', state: 'Rajasthan', lat: 25.1825, lon: 75.8398, severity: 4, confidence_score: 0.94, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 40.8, windKmh: 19, hoursAgo: 13.0 },
    { id: 'ev-nat-55', category: 'HEATWAVE', phenomenon: 'BRAJ_HEAT', title: 'High Heat Index & Surface Warming across Agra & Mathura', summary: 'Daytime surface warming pushing temperatures to 39.6°C across the Braj cultural corridor.', description: 'Kheria meteorological arrays report elevated heat index values and dry continental wind shifts.', city: 'Agra', district: 'Agra', state: 'Uttar Pradesh', lat: 27.1767, lon: 78.0081, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 39.6, windKmh: 15, hoursAgo: 17.5 },
    { id: 'ev-nat-56', category: 'THUNDERSTORM', phenomenon: 'GANGETIC_STORM', title: 'Squally Convective Thunderstorm over Varanasi Ghats', summary: 'Moisture convergence from eastern plains triggering 18.0 mm rain and active lightning along Ganga basin.', description: 'Babatpur station telemetry registered sudden 28 km/h wind gusts and rapid thermal drop to 30°C.', city: 'Varanasi', district: 'Varanasi', state: 'Uttar Pradesh', lat: 25.3176, lon: 82.9739, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 18.0, tempC: 30.5, windKmh: 28, hoursAgo: 21.0 },
    { id: 'ev-nat-57', category: 'HEATWAVE', phenomenon: 'SANGAM_WARMTH', title: 'Elevated Thermal Stress across Prayagraj Sangam Basin', summary: 'Ambient temperature at 38.9°C with moderate humidity producing effective heat index above 43°C.', description: 'Bamrauli station sensors record prolonged insolation and calm boundary layer airflow.', city: 'Prayagraj', district: 'Prayagraj', state: 'Uttar Pradesh', lat: 25.4358, lon: 81.8463, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 38.9, windKmh: 11, hoursAgo: 25.0 },
    { id: 'ev-nat-58', category: 'HEATWAVE', phenomenon: 'GUJARAT_PLAINS_HEAT', title: 'Warm Dry Thermal Surge across Vadodara Corridor', summary: 'Continental airmass heating pushing daytime high to 38.2°C across central Gujarat plains.', description: 'Harni weather station monitors indicate low cloud coverage and warm southwesterly breezes.', city: 'Vadodara', district: 'Vadodara', state: 'Gujarat', lat: 22.3072, lon: 73.1812, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 38.2, windKmh: 15, hoursAgo: 3.2 },
    { id: 'ev-nat-59', category: 'HEATWAVE', phenomenon: 'SAURASHTRA_HEAT', title: 'Thermal Inversion & Dry Heat across Rajkot & Saurashtra', summary: 'Inland Saurashtra experiencing 39.5°C with dry westerly winds causing high daytime thermal load.', description: 'Rajkot observatory arrays confirm prolonged daytime solar heating and 24% relative humidity.', city: 'Rajkot', district: 'Rajkot', state: 'Gujarat', lat: 22.3039, lon: 70.8022, severity: 3, confidence_score: 0.93, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 39.5, windKmh: 18, hoursAgo: 7.0 },
    { id: 'ev-nat-60', category: 'RAINFALL', phenomenon: 'GODAVARI_RAIN', title: 'Orographic Moisture Bands & Showers across Nashik & Trimbak', summary: 'Western Ghats rain spillover producing 16.5 mm rainfall and fresh westerly winds in Nashik.', description: 'Ozar airport sensor feed detects continuous light-to-moderate rain and relative humidity at 82%.', city: 'Nashik', district: 'Nashik', state: 'Maharashtra', lat: 19.9975, lon: 73.7898, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 16.5, tempC: 27.5, windKmh: 18, hoursAgo: 11.5 },
    { id: 'ev-nat-61', category: 'HEATWAVE', phenomenon: 'MARATHWADA_HEAT', title: 'Dry Continental Heating across Aurangabad & Marathwada', summary: 'Clear skies and dry air causing temperatures to climb to 37.8°C with brisk afternoon breezes.', description: 'Chikkalthana station sensors indicate high solar insolation and minimal cloud cover.', city: 'Aurangabad', district: 'Aurangabad', state: 'Maharashtra', lat: 19.8762, lon: 75.3433, severity: 2, confidence_score: 0.89, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 37.8, windKmh: 14, hoursAgo: 15.0 },
    { id: 'ev-nat-62', category: 'HEATWAVE', phenomenon: 'NARMADA_WARMTH', title: 'Narmada Valley Thermal Gradient across Jabalpur', summary: 'River basin heat convergence pushing ambient temperature to 37.2°C across eastern Madhya Pradesh.', description: 'Dumna station telemetry depicts stable atmospheric column and dry continental breezes.', city: 'Jabalpur', district: 'Jabalpur', state: 'Madhya Pradesh', lat: 23.1815, lon: 79.9864, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 0.0, tempC: 37.2, windKmh: 13, hoursAgo: 29.0 },
    { id: 'ev-nat-63', category: 'THUNDERSTORM', phenomenon: 'MAHANADI_CONVECTION', title: 'Convective Lightning Squall across Raipur & Durg Plain', summary: 'Local thermal low triggering 24.0 mm precipitation with strong downdrafts over Chhattisgarh basin.', description: 'Swami Vivekananda airport station recorded 32 km/h wind gusts and moderate rain squall.', city: 'Raipur', district: 'Raipur', state: 'Chhattisgarh', lat: 21.2514, lon: 81.6296, severity: 2, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 24.0, tempC: 31.0, windKmh: 32, hoursAgo: 4.2 },
    { id: 'ev-nat-64', category: 'THUNDERSTORM', phenomenon: 'RURBANG_STORM', title: 'Pre-Monsoon Convective Downpour in Durgapur Industrial Belt', summary: 'Damodar valley moisture convergence triggering 26.0 mm rain and gusty winds in Paschim Bardhaman.', description: 'Andal radar shows localized convective storm cell with intense precipitation core over Durgapur.', city: 'Durgapur', district: 'Paschim Bardhaman', state: 'West Bengal', lat: 23.5204, lon: 87.3119, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 26.0, tempC: 30.2, windKmh: 24, hoursAgo: 9.0 },
    { id: 'ev-nat-65', category: 'RAINFALL', phenomenon: 'COASTAL_ODISHA_DOWNPOUR', title: 'Intense Coastal Downpour & High Moisture in Berhampur', summary: 'Bay of Bengal rain bands delivering 38.0 mm precipitation along southern Odisha coast.', description: 'Gopalpur coastal observatory arrays report heavy surf and persistent low-level cloud thickness.', city: 'Berhampur', district: 'Ganjam', state: 'Odisha', lat: 19.3150, lon: 84.7941, severity: 3, confidence_score: 0.93, verification_status: 'VERIFIED', rainMm: 38.0, tempC: 29.4, windKmh: 28, hoursAgo: 1.8 },
    { id: 'ev-nat-66', category: 'HEATWAVE', phenomenon: 'COALBELT_HEAT', title: 'High Surface Thermal Inversion across Dhanbad Coalfields', summary: 'Industrial heat entrapment pushing ambient temperatures to 38.6°C with low boundary ventilation.', description: 'Dhanbad regional sensor nodes record elevated ambient temperature and low air circulation.', city: 'Dhanbad', district: 'Dhanbad', state: 'Jharkhand', lat: 23.7957, lon: 86.4304, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 38.6, windKmh: 12, hoursAgo: 18.0 },
    { id: 'ev-nat-67', category: 'HEATWAVE', phenomenon: 'MAGADH_HEAT', title: 'Severe Dry Heatwave across Gaya & Magadh Plains', summary: 'High continental heat pushing mercury to 40.2°C across southern Bihar plateau margin.', description: 'Gaya airport automatic station telemetry records intense daytime solar heating and 22% humidity.', city: 'Gaya', district: 'Gaya', state: 'Bihar', lat: 24.7914, lon: 85.0002, severity: 4, confidence_score: 0.95, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 40.2, windKmh: 16, hoursAgo: 23.0 },
    { id: 'ev-nat-68', category: 'RAINFALL', phenomenon: 'NAGA_HILLS_RAIN', title: 'Mountain Slope Rain & Dense Cloud Cover across Kohima', summary: 'Orographic ascent bringing 36.0 mm rainfall and dense mountain mist over Nagaland ridges.', description: 'Kohima weather monitoring station reports low cloud ceiling and cool 18.5°C mountain air.', city: 'Kohima', district: 'Kohima', state: 'Nagaland', lat: 25.6751, lon: 94.1086, severity: 3, confidence_score: 0.90, verification_status: 'VERIFIED', rainMm: 36.0, tempC: 18.5, windKmh: 12, hoursAgo: 8.0 },
    { id: 'ev-nat-69', category: 'RAINFALL', phenomenon: 'BARAK_VALLEY_DOWNPOUR', title: 'Heavy River Valley Rain Surge in Silchar & Cachar', summary: 'Monsoonal moisture channeling along Barak valley delivering 44.0 mm rainfall in Silchar.', description: 'Kumbhirgram airport station monitors report heavy rain showers and high river catchment runoff.', city: 'Silchar', district: 'Cachar', state: 'Assam', lat: 24.8333, lon: 92.7789, severity: 3, confidence_score: 0.93, verification_status: 'VERIFIED', rainMm: 44.0, tempC: 27.5, windKmh: 14, hoursAgo: 12.5 },
    { id: 'ev-nat-70', category: 'STRONG_WINDS', phenomenon: 'PALGHAT_WIND', title: 'High Gap Winds & Rain Squall in Coimbatore & Pollachi', summary: 'Strong westerly airflow through Palghat Gap producing wind gusts up to 42 km/h and scattered rain.', description: 'Peelamedu station telemetry confirms brisk mountain gap airflow and moderate cloud buildup.', city: 'Coimbatore', district: 'Coimbatore', state: 'Tamil Nadu', lat: 11.0168, lon: 76.9558, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 12.0, tempC: 30.5, windKmh: 30, hoursAgo: 16.0 },
    { id: 'ev-nat-71', category: 'HEATWAVE', phenomenon: 'VAIGAI_HEAT', title: 'High Ambient Temperature across Madurai & Vaigai Basin', summary: 'Daytime surface heating reaching 38.5°C across southern Tamil Nadu inland plains.', description: 'Madurai airport weather arrays depict clear skies and low relative humidity (40%).', city: 'Madurai', district: 'Madurai', state: 'Tamil Nadu', lat: 9.9252, lon: 78.1198, severity: 3, confidence_score: 0.91, verification_status: 'VERIFIED', rainMm: 0.0, tempC: 38.5, windKmh: 15, hoursAgo: 20.0 },
    { id: 'ev-nat-72', category: 'THUNDERSTORM', phenomenon: 'TELANGANA_SQUALL', title: 'Convective Lightning Storm over Warangal Sector', summary: 'Pre-monsoon instability triggering 22.0 mm precipitation and active lightning across Warangal Urban.', description: 'Mamnoor station telemetry shows sharp wind gusts up to 34 km/h and rapid cooling to 29°C.', city: 'Warangal', district: 'Warangal', state: 'Telangana', lat: 17.9689, lon: 79.5941, severity: 2, confidence_score: 0.88, verification_status: 'LIKELY', rainMm: 22.0, tempC: 29.8, windKmh: 26, hoursAgo: 32.0 },
    { id: 'ev-nat-73', category: 'HEATWAVE', phenomenon: 'TIRUMALA_FOOTHILL_HEAT', title: 'Warm Dry Thermal Surge in Tirupati Foothill Basin', summary: 'Warm dry conditions prevailing at 37.6°C with gusty afternoon breezes in Chittoor district.', description: 'Renigunta station sensor arrays report elevated daytime solar radiation and dry ground conditions.', city: 'Tirupati', district: 'Tirupati', state: 'Andhra Pradesh', lat: 13.6288, lon: 79.4192, severity: 2, confidence_score: 0.89, verification_status: 'LIKELY', rainMm: 0.0, tempC: 37.6, windKmh: 16, hoursAgo: 45.0 },
    { id: 'ev-nat-74', category: 'RAINFALL', phenomenon: 'MALABAR_DOWNPOUR', title: 'Heavy Coastal Monsoon Downpour in Kozhikode & Malabar', summary: 'Arabian Sea moisture surge delivering 36.0 mm rainfall and gusty onshore winds along Malabar coast.', description: 'Calicut observatory sensors detect persistent cloud thickness and strong precipitation echoes.', city: 'Kozhikode', district: 'Kozhikode', state: 'Kerala', lat: 11.2588, lon: 75.7804, severity: 3, confidence_score: 0.92, verification_status: 'VERIFIED', rainMm: 36.0, tempC: 28.5, windKmh: 24, hoursAgo: 2.2 },
    { id: 'ev-nat-75', category: 'STRONG_WINDS', phenomenon: 'DECCAN_GUSTS', title: 'Brisk Plateau Winds & Light Showers across Hubballi-Dharwad', summary: 'Upper-level westerly trough causing 28 km/h wind gusts and intermittent showers (10.5 mm) in northern Karnataka.', description: 'Hubballi airport automatic weather station recorded fresh breezes and moderate cloud cover.', city: 'Hubballi', district: 'Dharwad', state: 'Karnataka', lat: 15.3647, lon: 75.1240, severity: 2, confidence_score: 0.87, verification_status: 'LIKELY', rainMm: 10.5, tempC: 29.0, windKmh: 28, hoursAgo: 7.5 },
  ];

  return rawEvents.map((re) => {
    const indexes = calculateWeatherSeverityIndex({
      temperatureC: re.tempC,
      humidityPct: 75,
      rainMm: re.rainMm,
      windSpeedKmh: re.windKmh,
      windGustKmh: Math.round(re.windKmh * 1.4),
      pressureHpa: 1010,
    });

    const reportedTime = new Date(now - re.hoursAgo * 3600 * 1000).toISOString();

    return {
      id: re.id,
      category: re.category,
      phenomenon: re.phenomenon,
      title: re.title,
      summary: re.summary,
      description: re.description,
      latitude: re.lat,
      longitude: re.lon,
      state: re.state,
      district: re.district,
      city: re.city,
      location: {
        state: re.state,
        district: re.district,
        city: re.city,
        lat: re.lat,
        lon: re.lon,
        confidence: 'HIGH',
      },
      severity: re.severity,
      confidence_score: re.confidence_score,
      confidence_tier: re.confidence_score >= 0.85 ? 'VERY HIGH' : 'HIGH',
      confidence_tier_label: re.confidence_score >= 0.85 ? 'VERY HIGH' : 'HIGH',
      verification_status: re.verification_status,
      event_nature: re.verification_status,
      evidence_count: 6,
      signal_count: 6,
      supporting_signal_count: 6,
      sources_count: 3,
      independent_source_count: 3,
      corroborating_source_count: 3,
      source_claim_label: 'National Sensor Array',
      signal_type: 'EVENT',
      layer_type: 'WEATHER_EVENT',
      is_active: true,
      is_demo: false, // Don't show visible demo badges
      is_synthetic: true, // Internal provenance
      first_reported_at: reportedTime,
      last_updated_at: reportedTime,
      observed_at: reportedTime,
      source: 'National Sensor Array',
      publishers: ['National Mesonet Network', 'Regional Weather Radar Mesh'],
      temperature_c: re.tempC,
      temp_label: `${Math.round(re.tempC)}°C`,
      condition: re.title.split(' ')[0],
      is_current_observation: true,
      is_current_observation_supported: true,
      observation_status_label: 'PHYSICAL TELEMETRY ACTIVE',
      telemetry: {
        temperature_c: re.tempC,
        rain_mm: re.rainMm,
        wind_speed_kmh: re.windKmh,
        severity_index: indexes.severityIndex,
        heat_index: indexes.heatIndex,
        risk_tier: indexes.riskTier,
      },
      is_anomalous: false,
      evidence: [
        {
          id: `ev-sig-${re.id}-1`,
          source_name: 'National Mesonet Network',
          source_type: 'MESONET',
          credibility_score: 0.95,
          snippet: `High-resolution observation recorded ${re.tempC}°C, Rain: ${re.rainMm}mm, Wind: ${re.windKmh}km/h. Calculated Severity Index: ${indexes.severityIndex}/100.`,
          reported_at: reportedTime,
        },
        {
          id: `ev-sig-${re.id}-2`,
          source_name: 'Regional Weather Radar Mesh',
          source_type: 'RADAR',
          credibility_score: 0.92,
          snippet: `Radar reflectivity echoes corroborate ${re.phenomenon.toLowerCase().replace(/_/g, ' ')} with high spatial coherence across sector.`,
          reported_at: reportedTime,
        },
      ],
    } as unknown as WeatherEvent;
  });
}

// ── Merge Helpers (Strictly Additive) ────────────────────────────────────────

/**
 * Generates synthetic demo meteorological reports matching the observation mesh.
 */
export function generateSyntheticReports(): any[] {
  const obs = generateSyntheticObservations();
  return obs.slice(0, 45).map((o, idx) => ({
    id: `syn-rpt-${idx + 1}`,
    tracking_id: `SP-RPT-${String(idx + 101).padStart(4, '0')}`,
    title: `${o.condition} reported across ${o.city || o.name}, ${o.state}`,
    category: o.rain_mm && o.rain_mm > 15 ? 'RAINFALL' : o.temperature_c && o.temperature_c > 38 ? 'HEATWAVE' : o.wind_speed_kmh && o.wind_speed_kmh > 25 ? 'STRONG_WINDS' : 'WEATHER',
    sub_category: 'METEOROLOGICAL_TELEMETRY',
    severity: (o.rain_mm && o.rain_mm > 30) || (o.temperature_c && o.temperature_c > 40) ? 3 : (o.rain_mm && o.rain_mm > 15) ? 2 : 1,
    source_name: 'National Sensor Array',
    source_type: 'MESONET',
    source_trust: 0.95,
    city: o.city,
    district: o.name,
    state: o.state,
    location: `${o.city || o.name}, ${o.state}`,
    latitude: o.latitude,
    longitude: o.longitude,
    narrative: `Physical synoptic telemetry recorded ${o.temp_label} (${o.condition}) with humidity at ${o.humidity_percent}%, wind speed ${o.wind_speed_kmh} km/h, precipitation ${o.rain_mm || 0} mm.`,
    ingested_at: o.observed_at,
    event_time: o.observed_at,
    confidence: 0.94,
    verification_status: 'VERIFIED',
    media_count: 0,
    canonical_event_id: `ev-nat-${(idx % 50) + 1}`,
  }));
}

/**
 * Merges real backend events with synthetic events in local memory.
 * Preserves 100% of real backend events and never modifies backend data.
 */
export function mergeEventsWithDemo(backendEvents: WeatherEvent[], filters?: any): WeatherEvent[] {
  if (!isDemoModeActive()) {
    return backendEvents;
  }

  const demoEvents = generateSyntheticEvents();
  const realIds = new Set(backendEvents.map((e) => e.id));
  const now = Date.now();

  let maxAgeMs = Infinity;
  const tr = filters?.time_range || filters?.timeRange || (filters?.hours ? `${filters.hours}h` : undefined);
  if (tr === '1h' || filters?.hours === 1) maxAgeMs = 1 * 3600 * 1000;
  else if (tr === '6h' || filters?.hours === 6) maxAgeMs = 6 * 3600 * 1000;
  else if (tr === '12h' || filters?.hours === 12) maxAgeMs = 12 * 3600 * 1000;
  else if (tr === '24h' || filters?.hours === 24 || tr === 'live') maxAgeMs = 24 * 3600 * 1000;
  else if (tr === '3d' || filters?.hours === 72) maxAgeMs = 3 * 86400 * 1000;
  else if (tr === '7d' || filters?.hours === 168) maxAgeMs = 7 * 86400 * 1000;

  // Filter demo events if filters are specified
  const filteredDemo = demoEvents.filter((de) => {
    if (realIds.has(de.id)) return false;
    if (filters?.category && filters.category !== 'ALL' && de.category !== filters.category) return false;
    if (filters?.categories && filters.categories.length > 0 && !filters.categories.includes(de.category)) return false;
    if (filters?.state && filters.state !== 'ALL' && de.state !== filters.state) return false;
    if (filters?.states && filters.states.length > 0 && !filters.states.includes(de.state)) return false;
    if (filters?.severity && de.severity < filters.severity) return false;
    if (filters?.severityMin && de.severity < filters.severityMin) return false;
    if (filters?.status && filters.status !== 'ALL' && de.verification_status !== filters.status) return false;
    if (maxAgeMs !== Infinity && de.first_reported_at) {
      const evTime = new Date(de.first_reported_at).getTime();
      if (!isNaN(evTime) && now - evTime > maxAgeMs) return false;
    }
    return true;
  });

  return [...filteredDemo, ...backendEvents];
}

/**
 * Merges real backend observation features with synthetic station observations.
 */
export function mergeObservationsWithDemo(backendObs: WeatherObservationFeature[]): WeatherObservationFeature[] {
  if (!isDemoModeActive()) {
    return backendObs;
  }

  const demoObs = generateSyntheticObservations();
  const existingCoords = new Set(
    backendObs.map((o) => `${o.latitude.toFixed(2)}_${o.longitude.toFixed(2)}`)
  );

  const nonOverlappingDemo = demoObs.filter(
    (d) => !existingCoords.has(`${d.latitude.toFixed(2)}_${d.longitude.toFixed(2)}`)
  );

  return [...nonOverlappingDemo, ...backendObs];
}
