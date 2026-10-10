import { describe, test, expect, vi } from "vitest";

// Mock leaflet before any components are imported to avoid 'window is not defined'
vi.mock("leaflet", () => ({
  default: {
    icon: () => ({}),
    map: () => ({}),
  },
}));

import {
  normalizeStationName,
  findStationsInText,
  extractSegmentEndpoints,
  getSegmentStations,
  computeImpactedStations,
  getDistance,
  splitRouteIntoSegments,
} from "./DisruptionMap";
import { StationInfo, LineStationsData, DisruptionDetail } from "@/lib/types";

// Mock station dataset
const mockStations: StationInfo[] = [
  { name: "Balard", lat: 48.836, lon: 2.278, id: "balard" },
  { name: "Commerce", lat: 48.844, lon: 2.293, id: "commerce" },
  { name: "Concorde", lat: 48.865, lon: 2.321, id: "concorde" },
  { name: "République", lat: 48.867, lon: 2.363, id: "republique" },
  { name: "Charenton - Écoles", lat: 48.821, lon: 2.413, id: "charenton" },
  { name: "Vincennes", lat: 48.847, lon: 2.439, id: "vincennes" },
  { name: "Noisy-le-Grand Mont d'Est", lat: 48.843, lon: 2.583, id: "noisy_est" },
  { name: "Noisy-le-Grand", lat: 48.843, lon: 2.583, id: "noisy" }, // Subset name to test sorting
];

const mockLineData: LineStationsData = {
  stations: {
    "balard": { name: "Balard", lat: 48.836, lon: 2.278, neighbors: ["commerce"] },
    "commerce": { name: "Commerce", lat: 48.844, lon: 2.293, neighbors: ["balard", "concorde"] },
    "concorde": { name: "Concorde", lat: 48.865, lon: 2.321, neighbors: ["commerce", "republique"] },
    "republique": { name: "République", lat: 48.867, lon: 2.363, neighbors: ["concorde", "charenton"] },
    "charenton": { name: "Charenton - Écoles", lat: 48.821, lon: 2.413, neighbors: ["republique"] },
  }
};

describe("DisruptionMap NLP and Geographic Traversal Tests", () => {
  test("normalizeStationName strips accents and punctuation", () => {
    expect(normalizeStationName("République")).toBe("republique");
    expect(normalizeStationName("Noisy-le-Grand")).toBe("noisylegrand");
    expect(normalizeStationName("Charenton - Écoles")).toBe("charentonecoles");
  });

  test("findStationsInText matches longer names first to avoid substring matching", () => {
    const text = "Travaux à Noisy-le-Grand Mont d'Est";
    const matches = findStationsInText(text, mockStations);

    expect(matches.length).toBe(1);
    expect(matches[0].station.name).toBe("Noisy-le-Grand Mont d'Est");
  });

  test("extractSegmentEndpoints identifies start/end stations correctly", () => {
    const summary = "Trafic interrompu de Balard à Concorde";
    const text = "En raison de travaux de renouvellement de voies.";
    const endpoints = extractSegmentEndpoints(summary, text, mockStations);

    expect(endpoints).not.toBeNull();
    if (endpoints) {
      expect(endpoints[0].name).toBe("Balard");
      expect(endpoints[1].name).toBe("Concorde");
    }
  });

  test("extractSegmentEndpoints returns null if no segment keywords found", () => {
    const summary = "Panne de signalisation à République";
    const text = "Le trafic est perturbé sur l'ensemble de la ligne.";
    const endpoints = extractSegmentEndpoints(summary, text, mockStations);

    expect(endpoints).toBeNull();
  });

  test("getSegmentStations returns all stations between endpoints on a route", () => {
    const stA = mockStations[0]; // Balard
    const stB = mockStations[2]; // Concorde
    const impacted = getSegmentStations(stA, stB, mockLineData);

    expect(impacted.has("balard")).toBe(true);
    expect(impacted.has("commerce")).toBe(true);
    expect(impacted.has("concorde")).toBe(true);
    expect(impacted.has("republique")).toBe(false);
  });

  test("computeImpactedStations handles full line disruption fallback", () => {
    const disruption: DisruptionDetail = {
      id: "d1",
      impact_id: "imp1",
      line_code: "8",
      line_navitia_id: "C01378",
      line_name: "Ligne 8",
      line_color: "f6b23b",
      line_text_color: "000",
      summary: "Trafic interrompu sur toute la ligne",
      text: "Trafic interrompu sur toute la ligne en raison de travaux.",
      stations: "toute la ligne",
      date_debut: "2026-07-25",
      date_fin: "2026-07-26",
      cause: "travaux",
      effect: "interruption",
      periods: []
    };

    const impacted = computeImpactedStations(disruption, mockLineData);
    expect(impacted.size).toBe(Object.keys(mockLineData.stations).length);
    expect(impacted.has("republique")).toBe(true);
  });

  test("getDistance calculates correct Haversine distance in km", () => {
    const dist = getDistance(48.836, 2.278, 48.844, 2.293); // Balard to Commerce
    // Approximately 1.4km
    expect(dist).toBeGreaterThan(1.0);
    expect(dist).toBeLessThan(2.0);
  });

  test("splitRouteIntoSegments partitions tracks containing huge distance jumps", () => {
    const points = [
      { lat: 48.836, lon: 2.278 }, // Balard
      { lat: 48.844, lon: 2.293 }, // Commerce (close)
      { lat: 48.867, lon: 2.363 }, // République (approx 5.7km from Commerce)
      { lat: 48.821, lon: 2.413 }, // Charenton (approx 6.3km from République)
    ];

    // Using maxDistance = 3.5km, Commerce -> République and République -> Charenton are jumps
    const segments = splitRouteIntoSegments(points, 3.5);
    // Since each jump is larger than 3.5km, we get single points, and a segment requires at least 2 points
    // Let's test with a segment that has two close points, a jump, and another two close points
    const testPoints = [
      { lat: 48.836, lon: 2.278 }, // Balard
      { lat: 48.844, lon: 2.293 }, // Commerce (close to Balard)
      // JUMP TO VINCENNES
      { lat: 48.847, lon: 2.439 }, // Vincennes (approx 10.7km from Commerce)
      { lat: 48.843, lon: 2.583 }, // Noisy-le-Grand (approx 10.5km from Vincennes)
    ];

    // Under 12.0km (e.g. maxDistance = 5.0km), Commerce -> Vincennes is a jump (10.7km), but Balard->Commerce is close and Vincennes->Noisy is close (10.5km wait! Vincennes to Noisy is 10.5km so it's a jump for 5.0km maxDistance too!)
    // Let's choose points with known distance:
    // Balard -> Commerce is ~1.4km
    // Commerce -> Concorde is ~3.0km
    // Concorde -> République is ~3.1km
    // So all sequential distances are <= 3.5km
    // Let's inject a huge coordinates leap:
    const leapPoints = [
      { lat: 48.836, lon: 2.278 }, // Balard
      { lat: 48.844, lon: 2.293 }, // Commerce (~1.4km)
      // GIANT LEAP TO NEW YORK (approx 5800km)
      { lat: 40.712, lon: -74.006 }, // New York
      { lat: 40.758, lon: -73.985 }, // Times Square (~5.2km)
    ];

    // Using a 10.0km threshold, Balard->Commerce (1.4km) is connected. Commerce->NY is a leap (5800km) - split! NY->Times Square (5.2km) is connected.
    const splitSegs = splitRouteIntoSegments(leapPoints, 10.0);
    expect(splitSegs.length).toBe(2);
    expect(splitSegs[0].length).toBe(2); // [Balard, Commerce]
    expect(splitSegs[1].length).toBe(2); // [NY, Times Square]
  });
});

