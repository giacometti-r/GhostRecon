(() => {
  "use strict";
  const originalFetch = window.fetch.bind(window);
  let csrfToken = null;
  let csrfEnforced = false;
  const unsafe = new Set(["POST", "PUT", "PATCH", "DELETE"]);

  originalFetch("/auth/session", {
    credentials: "same-origin",
    headers: {"Accept": "application/json"}
  }).then((response) => {
    if (!response.ok) {
      window.location.assign("/auth/login?return_path=/");
      return null;
    }
    return response.json();
  }).then((payload) => {
    if (payload && typeof payload.csrf_token === "string") {
      csrfToken = payload.csrf_token;
      csrfEnforced = true;
    }
  }).catch(() => {
    csrfToken = null;
  });

  window.fetch = (input, init = {}) => {
    const target = new URL(
      typeof input === "string" ? input : input.url,
      window.location.href
    );
    const method = String(init.method || (input && input.method) || "GET").toUpperCase();
    if (csrfEnforced && target.origin === window.location.origin && unsafe.has(method)) {
      if (!csrfToken) {
        return Promise.reject(new Error("CSRF token is unavailable"));
      }
      const headers = new Headers(init.headers || (input && input.headers) || {});
      headers.set("X-CSRF-Token", csrfToken);
      init = {...init, headers, credentials: "same-origin"};
    }
    return originalFetch(input, init);
  };
})();
