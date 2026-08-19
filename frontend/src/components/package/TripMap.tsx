"use client";

import { useEffect, useId, useRef } from "react";

import type { DayPlan } from "@/types/package";
import styles from "@/styles/package.module.css";

type Marker = {
  lat: number;
  lon: number;
  label: string;
  day: number;
};

function collectMarkers(days: DayPlan[]): Marker[] {
  const markers: Marker[] = [];
  for (const day of days) {
    for (const item of day.schedule || []) {
      const lat = item.coordinates?.latitude;
      const lon = item.coordinates?.longitude;
      if (typeof lat === "number" && typeof lon === "number") {
        markers.push({ lat, lon, label: item.name || "Stop", day: day.day });
      }
    }
  }
  return markers;
}

export default function TripMap({ days }: { days: DayPlan[] }) {
  const id = useId().replace(/:/g, "");
  const mapRef = useRef<HTMLDivElement | null>(null);
  const markers = collectMarkers(days);
  const markerKey = markers.map((m) => `${m.day}:${m.lat}:${m.lon}`).join("|");

  useEffect(() => {
    if (!mapRef.current || markers.length === 0) {
      return;
    }

    let cancelled = false;
    let map: import("leaflet").Map | null = null;

    const start = async () => {
      const L = await import("leaflet");
      await import("leaflet/dist/leaflet.css");
      if (cancelled || !mapRef.current) {
        return;
      }

      map = L.map(mapRef.current, { scrollWheelZoom: false }).setView(
        [markers[0].lat, markers[0].lon],
        8,
      );
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
      }).addTo(map);

      const latLngs: [number, number][] = [];
      markers.forEach((marker) => {
        latLngs.push([marker.lat, marker.lon]);
        L.circleMarker([marker.lat, marker.lon], {
          radius: 8,
          color: "#145c3a",
          fillColor: "#c4a35a",
          fillOpacity: 0.95,
          weight: 2,
        })
          .bindPopup(`<strong>${marker.label}</strong>`)
          .addTo(map as import("leaflet").Map);
      });
      if (latLngs.length > 1 && map) {
        L.polyline(latLngs, { color: "#145c3a", weight: 3, opacity: 0.7 }).addTo(map);
        map.fitBounds(latLngs, { padding: [28, 28] });
      }
    };

    start();
    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [id, markerKey]);

  if (markers.length === 0) {
    return (
      <div className={styles.mapCard}>
        <div className={styles.panel}>
          <h3 className={styles.sectionTitle}>Route map</h3>
          <p className={styles.sectionLead}>
            Coordinates are shown only when a listing includes GPS. This trip
            does not have enough mapped points yet.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.mapCard}>
      <div ref={mapRef} className={styles.mapInner} />
    </div>
  );
}
