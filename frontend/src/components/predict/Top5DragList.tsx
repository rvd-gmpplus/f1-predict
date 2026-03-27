"use client";

import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Driver, Team } from "@/types";

interface Top5DragListProps {
  label: string;
  selectedDriverIds: number[];
  onOrderChange: (driverIds: number[]) => void;
  drivers: Driver[];
  teams: Team[];
  onAddDriver: () => void;
  onRemoveDriver: (driverId: number) => void;
  disabled?: boolean;
}

function SortableDriverItem({
  driverId,
  position,
  drivers,
  teams,
  onRemove,
  disabled,
}: {
  driverId: number;
  position: number;
  drivers: Driver[];
  teams: Team[];
  onRemove: () => void;
  disabled?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id: driverId, disabled });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const driver = drivers.find((d) => d.id === driverId);
  const team = driver ? teams.find((t) => t.id === driver.team_id) : null;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 bg-f1-surface/80 border border-f1-border rounded-lg px-4 py-3 group"
    >
      {!disabled && (
        <button
          className="cursor-grab active:cursor-grabbing text-f1-muted hover:text-white touch-none"
          {...attributes}
          {...listeners}
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
            <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="2" fill="none" />
          </svg>
        </button>
      )}

      <span className="text-f1-red font-mono font-bold text-sm w-6">
        P{position}
      </span>

      {driver && (
        <>
          <span
            className="w-1 h-5 rounded-full"
            style={{ backgroundColor: team?.color_hex ?? "#666" }}
          />
          <span className="font-medium text-sm flex-1">
            {driver.code}{" "}
            <span className="text-f1-muted">{driver.full_name}</span>
          </span>
        </>
      )}

      {!disabled && (
        <button
          onClick={onRemove}
          className="text-f1-muted hover:text-f1-red opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}

export function Top5DragList({
  label,
  selectedDriverIds,
  onOrderChange,
  drivers,
  teams,
  onAddDriver,
  onRemoveDriver,
  disabled = false,
}: Top5DragListProps) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = selectedDriverIds.indexOf(active.id as number);
      const newIndex = selectedDriverIds.indexOf(over.id as number);
      onOrderChange(arrayMove(selectedDriverIds, oldIndex, newIndex));
    }
  };

  return (
    <div>
      <h3 className="text-sm font-medium text-gray-300 mb-3">{label}</h3>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={selectedDriverIds}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {selectedDriverIds.map((id, i) => (
              <SortableDriverItem
                key={id}
                driverId={id}
                position={i + 1}
                drivers={drivers}
                teams={teams}
                onRemove={() => onRemoveDriver(id)}
                disabled={disabled}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {selectedDriverIds.length < 5 && !disabled && (
        <button
          onClick={onAddDriver}
          className="mt-2 w-full py-3 border-2 border-dashed border-f1-border rounded-lg text-f1-muted hover:border-f1-red hover:text-f1-red transition-all text-sm"
        >
          + Add driver ({selectedDriverIds.length}/5)
        </button>
      )}
    </div>
  );
}
