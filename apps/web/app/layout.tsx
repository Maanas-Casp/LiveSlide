import type { Metadata } from "next";
import "./styles.css";
import "./roles.css";
import "./location.css";

export const metadata: Metadata = { title: "Liveslide | Officer Desk", description: "Landslide risk monitoring and review" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
