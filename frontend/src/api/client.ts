import axios from "axios";

import type { ErrorResponse } from "@/types/review";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60000,
  headers: {
    "Content-Type": "application/json",
  },
});

export class APIClientError extends Error {
  public readonly error: string;
  public readonly statusCode: number;

  public constructor({
    error,
    message,
    statusCode,
  }: {
    error: string;
    message: string;
    statusCode: number;
  }) {
    super(message);
    this.name = "APIClientError";
    this.error = error;
    this.statusCode = statusCode;
  }
}

export async function postJson<TResponse>(
  path: string,
  payload: unknown,
): Promise<TResponse> {
  try {
    const response = await client.post<TResponse>(path, payload);
    return response.data;
  } catch (error: unknown) {
    throw normalizeApiError(error);
  }
}

function normalizeApiError(error: unknown): APIClientError {
  if (axios.isAxiosError(error)) {
    const payload: unknown = error.response?.data;
    if (isErrorResponse(payload)) {
      return new APIClientError({
        error: payload.error,
        message: payload.detail,
        statusCode: payload.status_code,
      });
    }

    return new APIClientError({
      error: "request_failed",
      message: error.message || "Request failed.",
      statusCode: error.response?.status ?? 500,
    });
  }

  return new APIClientError({
    error: "unknown_error",
    message: "An unknown error occurred.",
    statusCode: 500,
  });
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const maybeError = value as Record<string, unknown>;
  return (
    typeof maybeError.error === "string" &&
    typeof maybeError.detail === "string" &&
    typeof maybeError.status_code === "number"
  );
}
