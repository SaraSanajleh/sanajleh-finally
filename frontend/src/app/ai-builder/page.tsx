"use client";

import dynamic from "next/dynamic";

const ReTourWizard = dynamic(() => import("@/components/wizard/ReTourWizard"), {
  ssr: false,
});

export default function AIBuilderPage() {
  return <ReTourWizard />;
}
