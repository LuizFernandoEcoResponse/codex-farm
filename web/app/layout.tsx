import type { Metadata } from "next";
import "./style.css";
export const metadata: Metadata={title:"CodexFarm | Mission Control",description:"Autonomous work, in the open."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="pt-BR"><body>{children}</body></html>}
