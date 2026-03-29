import {
  ArrowRightIcon,
  HeartPulseIcon,
  ShieldCheckIcon,
  StethoscopeIcon,
  UserRoundIcon,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LandingPage() {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#f5efe4] px-4 py-10">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(251,246,239,0.9),transparent_58%),radial-gradient(circle_at_bottom_right,rgba(236,228,214,0.7),transparent_45%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.25] [background-image:linear-gradient(to_right,rgba(148,163,184,0.12)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.12)_1px,transparent_1px)] [background-size:26px_26px]" />

      <main className="relative z-10 w-full max-w-5xl">
        <Card className="border-[#e7dccb] bg-[#fffaf2]/95 py-0 shadow-xl backdrop-blur">
          <CardHeader className="border-b border-[#eadfce] px-8 py-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-[#d8e6ea] bg-[#edf5f7] px-3 py-1 text-xs font-medium text-[#25536a]">
              <ShieldCheckIcon className="size-4" />
              安全医疗智能入口
            </div>
            <CardTitle className="mt-3 text-2xl leading-tight font-semibold text-[#3b2f23] md:text-3xl">
              MedAgent 医疗工作台
            </CardTitle>
            <p className="mt-2 text-sm text-[#6f6253] md:text-base">
              请选择您的身份进入对应工作区，系统将提供适配的问诊与协作流程。
            </p>
          </CardHeader>

          <CardContent className="grid gap-4 p-5 md:grid-cols-2 md:gap-5 md:p-8">
            <RoleEntryCard
              roleName="医生端"
              roleDesc="用于接诊分析、检查解读与临床辅助决策。"
              roleTips={[
                "支持病情评估与结构化病历整理",
                "支持多 Agent 会诊与风险质控流程",
                "默认进入专业工作台视图",
              ]}
              href="/workspace?role=doctor"
              icon={<StethoscopeIcon className="size-5" />}
              accentClass="border-[#bfe1d0] bg-[#e7f5ec] text-[#24543e]"
              buttonClass="bg-[#3d7f5f] text-[#fffaf1] hover:bg-[#356f53]"
            />
            <RoleEntryCard
              roleName="患者端"
              roleDesc="用于咨询问诊、报告解读与复诊沟通。"
              roleTips={[
                "引导式提问，快速整理主诉与症状",
                "自动生成就医沟通摘要和注意事项",
                "默认进入简洁对话视图",
              ]}
              href="/workspace?role=patient"
              icon={<UserRoundIcon className="size-5" />}
              accentClass="border-[#c9deec] bg-[#e9f3f9] text-[#1f4e67]"
              buttonClass="bg-[#4a7992] text-[#fffaf1] hover:bg-[#3f677d]"
            />
          </CardContent>

          <div className="border-t border-[#eadfce] px-8 py-4 text-xs text-[#7d705f]">
            提示：MedAgent 仅提供临床辅助建议，不替代医生最终诊断。
          </div>
        </Card>
      </main>
    </div>
  );
}

type RoleEntryCardProps = {
  roleName: string;
  roleDesc: string;
  roleTips: string[];
  href: string;
  icon: ReactNode;
  accentClass: string;
  buttonClass: string;
};

function RoleEntryCard({
  roleName,
  roleDesc,
  roleTips,
  href,
  icon,
  accentClass,
  buttonClass,
}: RoleEntryCardProps) {
  return (
    <Card className="border border-[#eadfce] bg-[#fffdf8] py-0">
      <CardHeader className="space-y-3 px-5 pt-5 pb-4">
        <div
          className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${accentClass}`}
        >
          {icon}
          <span>{roleName}</span>
        </div>
        <p className="text-sm text-[#6f6253]">{roleDesc}</p>
      </CardHeader>
      <CardContent className="px-5 pb-5">
        <div className="space-y-2">
          {roleTips.map((tip) => (
            <div
              key={tip}
              className="rounded-lg border border-[#ece4d7] bg-[#fff8ed] px-3 py-2 text-sm text-[#4f4438]"
            >
              <div className="flex items-start gap-2">
                <HeartPulseIcon className="mt-0.5 size-4 shrink-0 text-[#6f6253]" />
                <span>{tip}</span>
              </div>
            </div>
          ))}
        </div>
        <Button
          asChild
          className={`mt-5 h-11 w-full font-semibold ${buttonClass}`}
          size="lg"
        >
          <Link href={href}>
            进入{roleName}
            <ArrowRightIcon className="size-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
