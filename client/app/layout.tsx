import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Sky Secure Assistant',
  description: 'Zoho Projects assistant frontend',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
