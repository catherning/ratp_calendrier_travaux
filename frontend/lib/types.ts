export interface LineInfo {
  code: string;
  navitia_id: string;
  name: string;
  mode: "metro" | "rer" | "transilien";
  color: string;       // hex without #
  text_color: string;  // hex without #
  logo_url: string;
}

export interface DisruptionPeriod {
  period_index: number;
  date_debut: string;
  date_fin: string;
}

export interface DisruptionDetail {
  id: string;
  impact_id: string;
  line_code: string;
  line_navitia_id: string;
  line_name: string;
  line_color: string;
  line_text_color: string;
  summary: string;
  date_debut: string;  // ISO 8601 of earliest period
  date_fin: string;    // ISO 8601 of earliest period
  text: string;
  stations: string;
  cause: string;
  effect: string;
  impacts_itinerary?: boolean;
  periods: DisruptionPeriod[];
}

export interface PlaceResult {
  id: string;
  name: string;
  label: string;
  coord: { lat: string; lon: string };
}

export interface ItinerarySection {
  type: string;                  // "public_transport" | "street_network" | "waiting"
  mode?: string;                 // "walking" | "metro" | "rer" | "train" | ...
  line_code?: string;
  line_color?: string;
  line_text_color?: string;
  from_name: string;
  to_name: string;
  duration: number;
}

export interface JourneyItinerary {
  duration: number;
  departure_time: string;
  arrival_time: string;
  sections: ItinerarySection[];
  impacted_disruption_ids: string[];
}

export interface JourneyDisruptionResponse {
  itinerary: JourneyItinerary | null;
  itineraries: JourneyItinerary[];
  disruptions: DisruptionDetail[];
}

export interface StationInfo {
  id: string;
  name: string;
  lat: number;
  lon: number;
}

export interface LineStationsData {
  stations: StationInfo[];
  routes: StationInfo[][];
}
