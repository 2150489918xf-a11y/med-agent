"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Stage, Layer, Rect, Image as KonvaImage, Line, Text, Group, Transformer } from "react-konva";
import type Konva from "konva";

// ── Types ──────────────────────────────────────────────────────
export interface Finding {
  id: string;
  disease: string;
  confidence: number;
  ai_confidence?: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2] pixel coords
  location?: string;
  location_cn?: string;
  is_solid?: boolean;
  has_contour?: boolean;
  doctor_note?: string;
  reviewed_by_doctor?: boolean;
}

export interface BrushStroke {
  id: string;
  points: number[];
  color: string;
  strokeWidth: number;
  tool: "brush" | "eraser";
}

export type CanvasTool = "pointer" | "rect" | "brush" | "eraser";

interface BboxCanvasProps {
  imageUrl: string;
  findings: Finding[];
  brushStrokes: BrushStroke[];
  pendingBbox?: [number, number, number, number] | null; // Show preview while form is open
  selectedId: string | null;
  readonly: boolean;
  tool: CanvasTool;
  onFindingUpdate?: (id: string, patch: Partial<Finding>) => void;
  onPendingRect?: (bbox: [number, number, number, number]) => void;
  onFindingDelete?: (id: string) => void;
  onFindingSelect?: (id: string | null) => void;
  onBrushStrokeAdd?: (stroke: BrushStroke) => void;
  onBrushStrokeDelete?: (id: string) => void;
}

// ── Constants ──────────────────────────────────────────────────
const BBOX_STROKE = "rgba(20, 184, 166, 0.8)";
const BBOX_FILL = "rgba(20, 184, 166, 0.08)";
const BBOX_SELECTED_STROKE = "rgba(56, 189, 248, 1)";
const BBOX_SELECTED_FILL = "rgba(56, 189, 248, 0.12)";
const BBOX_DOCTOR_STROKE = "rgba(99, 179, 237, 0.9)";
const LABEL_BG = "rgba(20, 184, 166, 0.85)";
const LABEL_SELECTED_BG = "rgba(56, 189, 248, 0.9)";
const PENDING_STROKE = "rgba(251, 191, 36, 0.9)";
const PENDING_FILL = "rgba(251, 191, 36, 0.08)";
const BRUSH_COLOR = "#ff6b6b";
const MIN_ZOOM = 0.3;
const MAX_ZOOM = 5;

// ── SelectableRect (with Transformer) ─────────────────────────
function SelectableRect({
  finding,
  isSelected,
  isDraggable,
  scale,
  onSelect,
  onDragEnd,
  onTransformEnd,
}: {
  finding: Finding;
  isSelected: boolean;
  isDraggable: boolean;
  scale: number;
  onSelect: () => void;
  onDragEnd: (e: Konva.KonvaEventObject<DragEvent>) => void;
  onTransformEnd: (e: Konva.KonvaEventObject<Event>) => void;
}) {
  const rectRef = useRef<Konva.Rect>(null);
  const trRef = useRef<Konva.Transformer>(null);

  useEffect(() => {
    if (isSelected && trRef.current && rectRef.current) {
      trRef.current.nodes([rectRef.current]);
      trRef.current.getLayer()?.batchDraw();
    }
  }, [isSelected]);

  const [x1, y1, x2, y2] = finding.bbox;
  const w = x2 - x1;
  const h = y2 - y1;
  const isDoctor = finding.reviewed_by_doctor;
  const doctorTag = isDoctor ? " 👨‍⚕️" : "";
  const labelText = `#${finding.id.substring(0, 4)}: ${(finding.confidence * 100).toFixed(0)}% ${finding.disease}${doctorTag}`;
  const fontSize = Math.max(12, Math.min(16, w * 0.06)) / scale;

  const strokeColor = isSelected
    ? BBOX_SELECTED_STROKE
    : isDoctor
      ? BBOX_DOCTOR_STROKE
      : BBOX_STROKE;
  const fillColor = isSelected ? BBOX_SELECTED_FILL : BBOX_FILL;

  return (
    <Group>
      <Rect
        ref={rectRef}
        x={x1}
        y={y1}
        width={w}
        height={h}
        fill={fillColor}
        stroke={strokeColor}
        strokeWidth={Math.max(1.5, 2 / scale)}
        strokeScaleEnabled={false}
        draggable={isDraggable}
        onClick={onSelect}
        onTap={onSelect}
        onDragEnd={onDragEnd}
        onTransformEnd={onTransformEnd}
      />
      {/* Label background */}
      <Rect
        x={x1}
        y={y1 - fontSize * 1.6}
        width={labelText.length * fontSize * 0.55 + 8 / scale}
        height={fontSize * 1.4}
        fill={isSelected ? LABEL_SELECTED_BG : LABEL_BG}
        cornerRadius={2 / scale}
        listening={false}
      />
      {/* Label text */}
      <Text
        x={x1 + 4 / scale}
        y={y1 - fontSize * 1.4}
        text={labelText}
        fontSize={fontSize}
        fontFamily="monospace"
        fill="white"
        listening={false}
      />
      {/* Transformer for resize — only on selected, non-readonly */}
      {isSelected && isDraggable && (
        <Transformer
          ref={trRef}
          rotateEnabled={false}
          keepRatio={false}
          enabledAnchors={[
            "top-left", "top-center", "top-right",
            "middle-left", "middle-right",
            "bottom-left", "bottom-center", "bottom-right",
          ]}
          borderStroke={BBOX_SELECTED_STROKE}
          anchorStroke={BBOX_SELECTED_STROKE}
          anchorFill="#ffffff"
          anchorSize={12 / scale}
          hitStrokeWidth={12 / scale}
          borderStrokeWidth={1.5 / scale}
          anchorCornerRadius={2 / scale}
        />
      )}
    </Group>
  );
}

// ── Main Component ──────────────────────────────────────────────
export function BboxCanvas({
  imageUrl,
  findings,
  brushStrokes,
  pendingBbox,
  selectedId,
  readonly,
  tool,
  onFindingUpdate,
  onPendingRect,
  onFindingDelete,
  onFindingSelect,
  onBrushStrokeAdd,
}: BboxCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [stageSize, setStageSize] = useState({ width: 600, height: 600 });
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
  const [drawRect, setDrawRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [currentBrush, setCurrentBrush] = useState<number[]>([]);

  // Load image
  useEffect(() => {
    if (!imageUrl) return;
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => setImage(img);
    img.src = imageUrl;
  }, [imageUrl]);

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setStageSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Fit image to container on load
  useEffect(() => {
    if (!image || stageSize.width === 0) return;
    const scaleX = stageSize.width / image.width;
    const scaleY = stageSize.height / image.height;
    const fitScale = Math.min(scaleX, scaleY, 1);
    setScale(fitScale);
    setPosition({
      x: (stageSize.width - image.width * fitScale) / 2,
      y: (stageSize.height - image.height * fitScale) / 2,
    });
  }, [image, stageSize]);

  // ── Zoom (wheel) ──
  const handleWheel = useCallback(
    (e: Konva.KonvaEventObject<WheelEvent>) => {
      e.evt.preventDefault();
      const stage = stageRef.current;
      if (!stage) return;

      const oldScale = scale;
      const pointer = stage.getPointerPosition();
      if (!pointer) return;

      const direction = e.evt.deltaY < 0 ? 1 : -1;
      const factor = 1.08;
      const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, direction > 0 ? oldScale * factor : oldScale / factor));

      const mousePointTo = {
        x: (pointer.x - position.x) / oldScale,
        y: (pointer.y - position.y) / oldScale,
      };

      setScale(newScale);
      setPosition({
        x: pointer.x - mousePointTo.x * newScale,
        y: pointer.y - mousePointTo.y * newScale,
      });
    },
    [scale, position],
  );

  // ── Get pointer position in image coordinates ──
  const getImagePos = useCallback((): { x: number; y: number } | null => {
    const stage = stageRef.current;
    if (!stage) return null;
    const pointer = stage.getPointerPosition();
    if (!pointer) return null;
    return {
      x: (pointer.x - position.x) / scale,
      y: (pointer.y - position.y) / scale,
    };
  }, [scale, position]);

  // ── Mouse handlers for drawing ──
  const handleMouseDown = useCallback((e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (readonly) return;
    const pos = getImagePos();
    if (!pos) return;

    if (tool === "rect") {
      setIsDrawing(true);
      setDrawStart(pos);
      setDrawRect({ x: pos.x, y: pos.y, w: 0, h: 0 });
    } else if (tool === "brush" || tool === "eraser") {
      setIsDrawing(true);
      setCurrentBrush([pos.x, pos.y]);
    } else if (tool === "pointer") {
      // Deselect when clicking empty area
      const clickedEmpty = e.target === stageRef.current || e.target.name() === "backgroundImage";
      if (clickedEmpty) {
        onFindingSelect?.(null);
      }
    }
  }, [readonly, tool, getImagePos, onFindingSelect]);

  const handleMouseMove = useCallback(() => {
    if (!isDrawing || readonly) return;
    const pos = getImagePos();
    if (!pos) return;

    if (tool === "rect" && drawStart) {
      setDrawRect({
        x: Math.min(drawStart.x, pos.x),
        y: Math.min(drawStart.y, pos.y),
        w: Math.abs(pos.x - drawStart.x),
        h: Math.abs(pos.y - drawStart.y),
      });
    } else if (tool === "brush" || tool === "eraser") {
      setCurrentBrush((prev) => [...prev, pos.x, pos.y]);
    }
  }, [isDrawing, readonly, tool, drawStart, getImagePos]);

  const handleMouseUp = useCallback(() => {
    if (!isDrawing || readonly) return;
    setIsDrawing(false);

    if (tool === "rect" && drawRect && drawRect.w > 5 && drawRect.h > 5) {
      // Emit pending rect → parent will show form for doctor to fill details
      onPendingRect?.([drawRect.x, drawRect.y, drawRect.x + drawRect.w, drawRect.y + drawRect.h]);
    } else if ((tool === "brush" || tool === "eraser") && currentBrush.length > 2) {
      const stroke: BrushStroke = {
        id: Math.random().toString(36).substring(2, 10),
        points: currentBrush,
        color: tool === "eraser" ? "#000000" : BRUSH_COLOR,
        strokeWidth: tool === "eraser" ? 20 : 3,
        tool,
      };
      onBrushStrokeAdd?.(stroke);
    }

    setDrawStart(null);
    setDrawRect(null);
    setCurrentBrush([]);
  }, [isDrawing, readonly, tool, drawRect, currentBrush, onPendingRect, onBrushStrokeAdd]);

  // ── Keyboard handler ──
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (readonly || !selectedId) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        onFindingDelete?.(selectedId);
        onFindingSelect?.(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [readonly, selectedId, onFindingDelete, onFindingSelect]);

  // ── Drag handler for bbox ──
  const handleDragEnd = useCallback(
    (id: string, e: Konva.KonvaEventObject<DragEvent>) => {
      if (readonly) return;
      const node = e.target;
      const finding = findings.find((f) => f.id === id);
      if (!finding) return;
      const w = finding.bbox[2] - finding.bbox[0];
      const h = finding.bbox[3] - finding.bbox[1];
      onFindingUpdate?.(id, {
        bbox: [node.x(), node.y(), node.x() + w, node.y() + h],
        reviewed_by_doctor: true,
      });
    },
    [readonly, findings, onFindingUpdate],
  );

  // ── Transform handler for bbox resize ──
  const handleTransformEnd = useCallback(
    (id: string, e: Konva.KonvaEventObject<Event>) => {
      if (readonly) return;
      const node = e.target as Konva.Rect;
      const scaleX = node.scaleX();
      const scaleY = node.scaleY();
      // Reset scale and apply to width/height
      node.scaleX(1);
      node.scaleY(1);
      const x = node.x();
      const y = node.y();
      const w = Math.max(5, node.width() * scaleX);
      const h = Math.max(5, node.height() * scaleY);
      onFindingUpdate?.(id, {
        bbox: [x, y, x + w, y + h],
        reviewed_by_doctor: true,
      });
    },
    [readonly, onFindingUpdate],
  );

  const isDraggable = !readonly && tool === "pointer";
  const cursorClass =
    tool === "rect" ? "cursor-crosshair" :
    tool === "brush" ? "cursor-crosshair" :
    tool === "eraser" ? "cursor-cell" : "cursor-default";

  return (
    <div ref={containerRef} className={`w-full h-full bg-[#1a1a1a] rounded-lg overflow-hidden ${cursorClass}`}>
      <Stage
        ref={stageRef}
        width={stageSize.width}
        height={stageSize.height}
        scaleX={scale}
        scaleY={scale}
        x={position.x}
        y={position.y}
        draggable={tool === "pointer" && !isDrawing}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onDragEnd={(e) => {
          if (e.target === stageRef.current) {
            setPosition({ x: e.target.x(), y: e.target.y() });
          }
        }}
      >
        {/* Image layer */}
        <Layer>
          {image && <KonvaImage image={image} x={0} y={0} name="backgroundImage" />}
        </Layer>

        {/* Brush strokes layer */}
        <Layer>
          {brushStrokes.map((stroke) => (
            <Line
              key={stroke.id}
              points={stroke.points}
              stroke={stroke.color}
              strokeWidth={stroke.strokeWidth / scale}
              tension={0.5}
              lineCap="round"
              lineJoin="round"
              globalCompositeOperation={stroke.tool === "eraser" ? "destination-out" : "source-over"}
            />
          ))}
          {/* Current brush stroke being drawn */}
          {isDrawing && currentBrush.length > 0 && (
            <Line
              points={currentBrush}
              stroke={tool === "eraser" ? "#888" : BRUSH_COLOR}
              strokeWidth={(tool === "eraser" ? 20 : 3) / scale}
              tension={0.5}
              lineCap="round"
              lineJoin="round"
              dash={tool === "eraser" ? [5, 5] : undefined}
            />
          )}
        </Layer>

        {/* Bbox layer */}
        <Layer>
          {findings.map((f) => (
            <SelectableRect
              key={f.id}
              finding={f}
              isSelected={f.id === selectedId}
              isDraggable={isDraggable}
              scale={scale}
              onSelect={() => onFindingSelect?.(f.id)}
              onDragEnd={(e) => handleDragEnd(f.id, e)}
              onTransformEnd={(e) => handleTransformEnd(f.id, e)}
            />
          ))}

          {/* Pending bbox preview — shown while doctor fills in the form */}
          {pendingBbox && (
            <Group>
              <Rect
                x={pendingBbox[0]}
                y={pendingBbox[1]}
                width={pendingBbox[2] - pendingBbox[0]}
                height={pendingBbox[3] - pendingBbox[1]}
                fill={PENDING_FILL}
                stroke={PENDING_STROKE}
                strokeWidth={2.5 / scale}
                dash={[8 / scale, 4 / scale]}
                listening={false}
              />
              <Text
                x={pendingBbox[0] + 4 / scale}
                y={pendingBbox[1] + 4 / scale}
                text="📝 请填写病灶信息..."
                fontSize={14 / scale}
                fill="rgba(251, 191, 36, 0.9)"
                listening={false}
              />
            </Group>
          )}

          {/* Drawing preview rect */}
          {isDrawing && drawRect && tool === "rect" && (
            <Rect
              x={drawRect.x}
              y={drawRect.y}
              width={drawRect.w}
              height={drawRect.h}
              fill="rgba(56, 189, 248, 0.1)"
              stroke="rgba(56, 189, 248, 0.8)"
              strokeWidth={2 / scale}
              dash={[6 / scale, 3 / scale]}
            />
          )}
        </Layer>
      </Stage>
    </div>
  );
}
