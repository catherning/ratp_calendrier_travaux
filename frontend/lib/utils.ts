export function effectLabel(effect: string): string {
  const map: Record<string, string> = {
    NO_SERVICE: "Trafic interrompu",
    SIGNIFICANT_DELAYS: "Retards importants",
    REDUCED_SERVICE: "Service réduit",
    DETOUR: "Déviation",
    MODIFIED_SERVICE: "Service modifié",
  };
  return map[effect] ?? effect;
}

export function causeLabel(cause: string): string {
  const map: Record<string, string> = {
    travaux: "Travaux",
    incident: "Incident",
    perturbation: "Perturbation",
    maintenance: "Maintenance",
    delays: "Délais",
    hors_travaux: "Hors travaux",
  };
  const key = cause ? cause.toLowerCase() : "";
  return map[key] ?? (cause ? cause.charAt(0).toUpperCase() + cause.slice(1) : "Travaux");
}
