export function getErrorMessage(error: unknown): string {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object") {
    const candidate = error as {
      response?: { data?: { message?: string } };
      message?: string;
    };
    if (candidate.response?.data?.message) {
      return candidate.response.data.message;
    }
    if (candidate.message) {
      return candidate.message;
    }
  }
  return "请求失败，请稍后重试。";
}
