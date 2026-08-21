import { UserButton } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";

import { MeCard } from "./me-card";

export default async function DashboardPage() {
  const { userId } = await auth.protect();

  return (
    <main className="min-h-screen p-8">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-center justify-between border-b pb-4">
          <div>
            <p className="text-sm text-gray-500">
              Signed in as
            </p>

            <p className="font-mono text-sm">
              {userId}
            </p>
          </div>

          <UserButton />
        </div>

        <div className="mt-10">
          <h1 className="text-3xl font-bold">
            ForgeOps Dashboard
          </h1>

          <p className="mt-3 text-gray-600">
            Your authenticated ForgeOps identity.
          </p>
        </div>

        <div className="mt-8">
          <MeCard />
        </div>
      </div>
    </main>
  );
}