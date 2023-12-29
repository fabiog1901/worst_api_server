import axios from "axios";
import { useAuthStore } from "@/stores/authStore";

export const nextElementInList = <T>(arr: T[], val: T): T => {
  const idx = arr.indexOf(val);
  const nextIdx = (idx + 1) % arr.length;
  return arr[nextIdx];
};

export const formatDecimal = (value: any) => {
  if (value) {
    return value.toLocaleString(undefined, {
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    });
  }

  return "";
};

export const formatDate = (value: any) => {
  if (value) {
    return new Date(value).toDateString();
  }

  return "";
};

export const hashCode = (s: string) => {
  let hash = 0,
    i,
    chr;
  if (!s || s.length === 0) {
    return hash;
  }
  for (i = 0; i < s.length; i++) {
    chr = s.charCodeAt(i);
    hash = (hash << 5) - hash + chr;
    hash |= 0; // Convert to 32bit integer
  }
  return hash;
};

export const getLabel = (s: string) => {
  const crc = hashCode(s);
  switch (crc % 9) {
    case 0:
      return "bg-indigo-500 border rounded-2xl p-2";
    case 1:
      return "bg-purple-600 rounded-2xl p-2";
    case 2:
      return "bg-teal-400 rounded-2xl p-2";
    case 3:
      return "bg-orange-400 rounded-2xl p-2";
    case 4:
      return "bg-rose-500 rounded-2xl p-2";
    case 5:
      return "bg-amber-400 border rounded-2xl p-2";
    case 6:
      return "bg-lime-600 rounded-2xl p-2";
    case 7:
      return "bg-emerald-600 rounded-2xl p-2";
    case 8:
      return "bg-fuchsia-400 rounded-2xl p-2";
  }
};

export const titleCase = (s: string) =>
  s
    .replace(/^[-_]*(.)/, (_, c) => c.toUpperCase()) // Initial char (after -/_)
    .replace(/[-_]+(.)/g, (_, c) => "_" + c.toUpperCase()); // First char after each -/_

const { user, logout } = useAuthStore();

axios.defaults.baseURL = import.meta.env.VITE_APP_API_URL;
axios.defaults.headers.common["Authorization"] = `Bearer ${user.access_token}`;
axios.defaults.headers.post["Content-Type"] = "application/json";

export const axiosWrapper = {
  get: request("GET"),
  post: request("POST"),
  put: request("PUT"),
  delete: request("DELETE"),
};

function request(method: string) {
  return (url: string, body: any = {}) => {
    const config: any = {
      method: method,
      url: url,
      data: body,
      //data: new URLSearchParams(body),
    };

    return axios(config)
      .then((r) => {
        return r.data;
      })
      .catch((error) => {
        console.error(error.response);
        logout();
      });
  };
}
