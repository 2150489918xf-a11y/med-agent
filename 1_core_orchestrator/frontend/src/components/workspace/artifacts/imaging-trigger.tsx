"use client";

import { ScanLineIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useChatBox } from "../chats/chat-box";
import { Tooltip } from "../tooltip";

export function ImagingTrigger() {
  const { hasImaging, openImagingReview } = useChatBox();

  return (
    <Tooltip content={hasImaging ? "影像审核台" : "暂无待审核的影像报告"}>
      <Button
        variant="ghost"
        size="icon"
        className="text-muted-foreground hover:text-foreground relative h-8 w-8 transition-colors"
        onClick={openImagingReview}
        disabled={!hasImaging}
      >
        <ScanLineIcon className="h-4 w-4" />
        {hasImaging && (
          <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-500 opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500"></span>
          </span>
        )}
      </Button>
    </Tooltip>
  );
}
