import api from "./client";

/* =========================================================
   ENTITLEMENTS
   ========================================================= */

export async function getEntitlement(feature) {
  const response = await api.get(
    `/entitlements/${feature}`
  );

  return response.data;
}
