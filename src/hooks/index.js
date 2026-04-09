import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import * as api from "../api";

export function useFetch(fetchFn, deps = [], options = {}) {
  const { immediate = true, onError, onSuccess } = options;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);

  const execute = useCallback(
    async (...args) => {
      setLoading(true);
      setError(null);

      try {
        const result = await fetchFn(...args);
        setData(result);
        onSuccess?.(result);
        return result;
      } catch (err) {
        setError(err.message);
        onError?.(err);
        return null;
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps
  );

  useEffect(() => {
    if (immediate) {
      execute();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, execute, loading, setData };
}

export function useVariants(filters = {}) {
  const key = JSON.stringify(filters);
  return useFetch(() => api.getVariants(filters), [key]);
}

export function useVariant(variantId) {
  return useFetch(
    () => (variantId ? api.getVariant(variantId) : Promise.resolve(null)),
    [variantId],
    { immediate: Boolean(variantId) }
  );
}

export function useComparison(idA, idB) {
  return useFetch(
    () => (idA && idB ? api.compareVariants(idA, idB) : Promise.resolve(null)),
    [idA, idB],
    { immediate: Boolean(idA && idB) }
  );
}

export function useMatchScores() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const compute = useCallback(async (preferences) => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.getMatchScores(preferences);
      setResults(response);
      return response;
    } catch (err) {
      setError(err.message);
      toast.error("Could not compute match scores");
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  return { compute, error, loading, results };
}

export function useHospitals(params = {}) {
  const key = JSON.stringify(params);

  return useFetch(
    () =>
      params.city || params.pincode
        ? api.getHospitals(params)
        : Promise.resolve(null),
    [key],
    { immediate: Boolean(params.city || params.pincode) }
  );
}

export function useDocumentUpload() {
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const upload = useCallback(async (file) => {
    setUploading(true);
    setProgress(0);
    setError(null);

    try {
      const response = await api.uploadDocument(file, setProgress);
      toast.success("Document uploaded successfully");
      return response;
    } catch (err) {
      setError(err.message);
      toast.error(`Upload failed: ${err.message}`);
      return null;
    } finally {
      setUploading(false);
    }
  }, []);

  return { error, progress, upload, uploading };
}

export function useChat(contextType, contextId) {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);

  useEffect(() => {
    setMessages([]);
  }, [contextId, contextType]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();

      if (!trimmed) {
        return;
      }

      const userMsg = { role: "user", content: trimmed, id: Date.now() };
      const assistantMsg = {
        role: "assistant",
        content: "",
        id: Date.now() + 1,
        citations: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setStreaming(true);

      try {
        const body = await api.streamChatMessage({
          message: trimmed,
          context_type: contextType,
          context_id: contextId,
          history: messages
            .slice(-10)
            .map((message) => ({ role: message.role, content: message.content })),
        });

        const reader = body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const normalized = buffer.replace(/\r\n/g, "\n");
          const chunks = normalized.split("\n\n");
          buffer = chunks.pop() || "";

          for (const chunk of chunks) {
            if (!chunk.startsWith("data: ")) {
              continue;
            }

            try {
              const parsed = JSON.parse(chunk.slice(6));

              if (parsed.token) {
                setMessages((prev) =>
                  prev.map((message) =>
                    message.id === assistantMsg.id
                      ? { ...message, content: message.content + parsed.token }
                      : message
                  )
                );
              }

              if (parsed.citations) {
                setMessages((prev) =>
                  prev.map((message) =>
                    message.id === assistantMsg.id
                      ? { ...message, citations: parsed.citations }
                      : message
                  )
                );
              }

              if (parsed.caveat) {
                setMessages((prev) =>
                  prev.map((message) =>
                    message.id === assistantMsg.id
                      ? { ...message, caveat: parsed.caveat }
                      : message
                  )
                );
              }
            } catch (_) {
              // Ignore malformed SSE frames and keep streaming.
            }
          }
        }
      } catch (_) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMsg.id
              ? {
                  ...message,
                  content: "Sorry, I could not get a response. Please try again.",
                  error: true,
                }
              : message
          )
        );
      } finally {
        setStreaming(false);
      }
    },
    [contextId, contextType, messages]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { clearMessages, messages, sendMessage, streaming };
}

export function useClaimChecklist() {
  const [checklist, setChecklist] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generate = useCallback(async (payload) => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.getClaimChecklist(payload);
      setChecklist(response);
      return response;
    } catch (err) {
      setError(err.message);
      toast.error("Could not generate checklist");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { checklist, error, generate, loading };
}
