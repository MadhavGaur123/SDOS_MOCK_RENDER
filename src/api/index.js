import axios from "axios";

const BASE = process.env.REACT_APP_API_URL || "/api";

function normalizeErrorMessage(value) {
  if (value == null) {
    return null;
  }

  if (typeof value === "string") {
    return value;
  }

  if (Array.isArray(value)) {
    const parts = value
      .map((item) => normalizeErrorMessage(item))
      .filter(Boolean);
    return parts.length ? parts.join("; ") : null;
  }

  if (typeof value === "object") {
    if (typeof value.msg === "string") {
      const location = Array.isArray(value.loc) ? value.loc.join(".") : null;
      return location ? `${location}: ${value.msg}` : value.msg;
    }

    try {
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  }

  return String(value);
}

function cleanParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== "" && value !== null && value !== undefined
    )
  );
}

const client = axios.create({
  baseURL: BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("healin_token");

  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      normalizeErrorMessage(error.response?.data?.detail) ||
      normalizeErrorMessage(error.response?.data?.message) ||
      error.message ||
      "Something went wrong";

    return Promise.reject(new Error(message));
  }
);

export const getVariants = (params = {}) =>
  client.get("/variants", { params: cleanParams(params) }).then((response) => response.data);

export const getVariant = (variantId) =>
  client.get(`/variants/${variantId}`).then((response) => response.data);

export const getVariantExclusions = (variantId) =>
  client.get(`/variants/${variantId}/exclusions`).then((response) => response.data);

export const getVariantWaitingPeriods = (variantId) =>
  client
    .get(`/variants/${variantId}/waiting-periods`)
    .then((response) => response.data);

export const getVariantSublimits = (variantId) =>
  client.get(`/variants/${variantId}/sublimits`).then((response) => response.data);

export const compareVariants = (variantIdA, variantIdB) =>
  client
    .post("/compare", { variant_id_a: variantIdA, variant_id_b: variantIdB })
    .then((response) => response.data);

export const getMatchScores = (preferences) =>
  client.post("/match", preferences).then((response) => response.data);

export const getHospitals = (params = {}) =>
  client.get("/hospitals", { params: cleanParams(params) }).then((response) => response.data);

export const uploadDocument = (file, onProgress) => {
  const form = new FormData();
  form.append("file", file);

  return client
    .post("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: onProgress
        ? (event) => {
            const total = event.total || 1;
            onProgress(Math.round((event.loaded * 100) / total));
          }
        : undefined,
    })
    .then((response) => response.data);
};

export const deleteDocument = (docId) =>
  client.delete(`/documents/${docId}`).then((response) => response.data);

export const getMyDocuments = () =>
  client.get("/documents").then((response) => response.data);

export const sendChatMessage = (payload) =>
  client.post("/chat", payload).then((response) => response.data);

export const streamChatMessage = async (payload) => {
  const token = localStorage.getItem("healin_token");
  const headers = {
    "Accept": "text/event-stream",
    "Content-Type": "application/json",
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error("Chat stream failed");
  }

  return response.body;
};

export const getClaimChecklist = (payload) =>
  client.post("/claim-checklist", payload).then((response) => response.data);

export const admin = {
  createVariant: (data) =>
    client.post("/admin/variants", data).then((response) => response.data),
  deleteVariant: (id) =>
    client.delete(`/admin/variants/${id}`).then((response) => response.data),
  getRefreshLogs: () =>
    client.get("/admin/refresh-logs").then((response) => response.data),
  getVariants: (params = {}) =>
    client.get("/admin/variants", { params: cleanParams(params) }).then((response) => response.data),
  triggerRefresh: (sourceId) =>
    client.post(`/admin/refresh/${sourceId}`).then((response) => response.data),
  updateVariant: (id, data) =>
    client.put(`/admin/variants/${id}`, data).then((response) => response.data),
};

export default client;
