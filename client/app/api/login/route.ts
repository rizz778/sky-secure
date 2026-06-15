import { NextResponse } from "next/server";

export async function POST() {
  const url = process.env.BACKEND_URL ?? "http://localhost:8000";
  const loginUrl = `${url}/auth/login`;
  return NextResponse.redirect(loginUrl);
}
