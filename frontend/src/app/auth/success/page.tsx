"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

function AuthSuccessHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { handleOAuthToken } = useAuth();

  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      handleOAuthToken(token).then(() => {
        router.push("/dashboard");
      });
    } else {
      router.push("/auth/login");
    }
  }, [searchParams, handleOAuthToken, router]);

  return (
    <div className="card-glass p-8 text-center">
      <div className="animate-spin w-8 h-8 border-2 border-f1-red border-t-transparent rounded-full mx-auto mb-4" />
      <p className="text-gray-300">Completing sign in...</p>
    </div>
  );
}

export default function AuthSuccessPage() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Suspense
        fallback={
          <div className="card-glass p-8 text-center">
            <div className="animate-spin w-8 h-8 border-2 border-f1-red border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-gray-300">Loading...</p>
          </div>
        }
      >
        <AuthSuccessHandler />
      </Suspense>
    </div>
  );
}
