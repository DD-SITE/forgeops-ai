import Link from "next/link";
import {
  Show,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="min-h-screen">
      <nav className="flex items-center justify-between border-b px-6 py-4">
        <Link href="/" className="font-semibold">
          ForgeOps AI
        </Link>

        <div className="flex items-center gap-4">
          <Show when="signed-out">
            <SignInButton mode="modal">
              <button className="rounded-md border px-4 py-2 text-sm">
                Sign in
              </button>
            </SignInButton>

            <SignUpButton mode="modal">
              <button className="rounded-md bg-black px-4 py-2 text-sm text-white">
                Sign up
              </button>
            </SignUpButton>
          </Show>

          <Show when="signed-in">
            <Link
              href="/dashboard"
              className="text-sm underline"
            >
              Dashboard
            </Link>

            <UserButton />
          </Show>
        </div>
      </nav>

      <section className="mx-auto max-w-4xl px-6 py-24">
        <h1 className="text-5xl font-bold tracking-tight">
          ForgeOps AI
        </h1>

        <p className="mt-6 max-w-2xl text-lg text-gray-600">
          Engineering intelligence, retrieval-augmented generation,
          and agentic incident investigation.
        </p>
      </section>
    </main>
  );
}