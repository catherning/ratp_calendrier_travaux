/** Static line info for display — mirrors the backend registry. */
export const LINE_GROUPS = {
  metro: Array.from({ length: 14 }, (_, i) => String(i + 1)).concat(["15"]),
  rer: ["A", "B", "C", "D", "E"],
  transilien: ["H", "J", "K", "L", "N", "P", "R", "U"],
} as const;

/** Official RATP/SNCF brand hex colors (without #). */
export const LINE_COLORS: Record<string, { bg: string; text: string }> = {
  "1":  { bg: "FFCE00", text: "000000" },
  "2":  { bg: "0064B0", text: "FFFFFF" },
  "3":  { bg: "9F9825", text: "FFFFFF" },
  "4":  { bg: "C04191", text: "FFFFFF" },
  "5":  { bg: "F28E42", text: "000000" },
  "6":  { bg: "83C491", text: "000000" },
  "7":  { bg: "F3A4BA", text: "000000" },
  "8":  { bg: "CEADD2", text: "000000" },
  "9":  { bg: "D5C900", text: "000000" },
  "10": { bg: "E3B32A", text: "000000" },
  "11": { bg: "8D5E2A", text: "FFFFFF" },
  "12": { bg: "00814F", text: "FFFFFF" },
  "13": { bg: "98D4E2", text: "000000" },
  "14": { bg: "662483", text: "FFFFFF" },
  "15": { bg: "B90845", text: "FFFFFF" },
  "A":  { bg: "E3051C", text: "FFFFFF" },
  "B":  { bg: "5291CE", text: "FFFFFF" },
  "C":  { bg: "FFEA00", text: "000000" },
  "D":  { bg: "00A06E", text: "FFFFFF" },
  "E":  { bg: "B93684", text: "FFFFFF" },
  "H":  { bg: "6E6E00", text: "FFFFFF" },
  "J":  { bg: "C9A71C", text: "FFFFFF" },
  "K":  { bg: "9F9825", text: "FFFFFF" },
  "L":  { bg: "8DB7C8", text: "000000" },
  "N":  { bg: "004899", text: "FFFFFF" },
  "P":  { bg: "F0A500", text: "FFFFFF" },
  "R":  { bg: "E87B10", text: "FFFFFF" },
  "U":  { bg: "CE007C", text: "FFFFFF" },
};

const WIKI = "https://upload.wikimedia.org/wikipedia/commons/thumb";
const WIKI_F = "https://upload.wikimedia.org/wikipedia/commons";

export const LINE_LOGOS: Record<string, string> = {
  "1":  `${WIKI}/3/30/Paris_transit_icons_-_M%C3%A9tro_1.svg/60px-Paris_transit_icons_-_M%C3%A9tro_1.svg.png`,
  "2":  `${WIKI}/d/da/Paris_transit_icons_-_M%C3%A9tro_2.svg/60px-Paris_transit_icons_-_M%C3%A9tro_2.svg.png`,
  "3":  `${WIKI}/0/01/Paris_transit_icons_-_M%C3%A9tro_3.svg/60px-Paris_transit_icons_-_M%C3%A9tro_3.svg.png`,
  "4":  `${WIKI}/7/76/Paris_transit_icons_-_M%C3%A9tro_4.svg/60px-Paris_transit_icons_-_M%C3%A9tro_4.svg.png`,
  "5":  `${WIKI}/5/54/Paris_transit_icons_-_M%C3%A9tro_5.svg/60px-Paris_transit_icons_-_M%C3%A9tro_5.svg.png`,
  "6":  `${WIKI}/6/6f/Paris_transit_icons_-_M%C3%A9tro_6.svg/60px-Paris_transit_icons_-_M%C3%A9tro_6.svg.png`,
  "7":  `${WIKI}/2/21/Paris_transit_icons_-_M%C3%A9tro_7.svg/60px-Paris_transit_icons_-_M%C3%A9tro_7.svg.png`,
  "8":  `${WIKI}/e/e8/Paris_transit_icons_-_M%C3%A9tro_8.svg/60px-Paris_transit_icons_-_M%C3%A9tro_8.svg.png`,
  "9":  `${WIKI}/1/10/Paris_transit_icons_-_M%C3%A9tro_9.svg/60px-Paris_transit_icons_-_M%C3%A9tro_9.svg.png`,
  "10": `${WIKI}/2/24/Paris_transit_icons_-_M%C3%A9tro_10.svg/60px-Paris_transit_icons_-_M%C3%A9tro_10.svg.png`,
  "11": `${WIKI}/c/c1/Paris_transit_icons_-_M%C3%A9tro_11.svg/60px-Paris_transit_icons_-_M%C3%A9tro_11.svg.png`,
  "12": `${WIKI}/3/3f/Paris_transit_icons_-_M%C3%A9tro_12.svg/60px-Paris_transit_icons_-_M%C3%A9tro_12.svg.png`,
  "13": `${WIKI}/a/a9/Paris_transit_icons_-_M%C3%A9tro_13.svg/60px-Paris_transit_icons_-_M%C3%A9tro_13.svg.png`,
  "14": `${WIKI}/9/93/Paris_transit_icons_-_M%C3%A9tro_14.svg/60px-Paris_transit_icons_-_M%C3%A9tro_14.svg.png`,
  "15": `${WIKI}/5/55/Paris_transit_icons_-_M%C3%A9tro_15.svg/60px-Paris_transit_icons_-_M%C3%A9tro_15.svg.png`,
  "A":  `${WIKI_F}/4/4a/Paris_transit_icons_-_RER_A.svg`,
  "B":  `${WIKI_F}/f/fd/Paris_transit_icons_-_RER_B.svg`,
  "C":  `${WIKI_F}/e/e4/Paris_transit_icons_-_RER_C.svg`,
  "D":  `${WIKI_F}/4/4d/Paris_transit_icons_-_RER_D.svg`,
  "E":  `${WIKI_F}/2/25/Paris_transit_icons_-_RER_E.svg`,
  "H":  `${WIKI_F}/d/d6/Paris_transit_icons_-_Train_H.svg`,
  "J":  `${WIKI_F}/a/a5/Paris_transit_icons_-_Train_J.svg`,
  "K":  `${WIKI_F}/5/58/Paris_transit_icons_-_Train_K.svg`,
  "L":  `${WIKI_F}/b/b9/Paris_transit_icons_-_Train_L.svg`,
  "N":  `${WIKI_F}/f/f0/Paris_transit_icons_-_Train_N.svg`,
  "P":  `${WIKI_F}/4/41/Paris_transit_icons_-_Train_P.svg`,
  "R":  `${WIKI_F}/6/69/Paris_transit_icons_-_Train_R.svg`,
  "U":  `${WIKI_F}/9/9d/Paris_transit_icons_-_Train_U.svg`,
};

export function lineDisplayName(code: string): string {
  if (LINE_GROUPS.metro.includes(code as never)) return `M${code}`;
  if (LINE_GROUPS.rer.includes(code as never)) return `RER ${code}`;
  return `N ${code}`;
}
