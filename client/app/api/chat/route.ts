import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const url = process.env.BACKEND_URL ?? "http://localhost:8000";
  const body = await request.json();

  const response = await fetch(`${url}/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const text = await response.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { message: text || response.statusText || "Unable to parse backend response." };
  }

  return NextResponse.json(data ?? {}, {
    status: response.status,
  });
}
