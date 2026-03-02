import type { Metadata } from "next";
import { Manrope, Space_Grotesk } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-main",
  subsets: ["latin"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-accent",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DNS VPN Mini App",
  description: "Premium mini app for VPN, DNS and TON exchange",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className={`${manrope.variable} ${spaceGrotesk.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
