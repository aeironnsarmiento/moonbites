import { Button, HStack, Icon, Input, Text, Tooltip } from "@chakra-ui/react";
import { useState } from "react";

import "./ServingsStepper.scss";

type ServingsStepperProps = {
  currentServings: number;
  originalServings: number;
  isSaving?: boolean;
  onDecrement: () => void;
  onIncrement: () => void;
  onSaveDefault?: (servings: number) => Promise<void>;
};

function PencilIcon() {
  return (
    <Icon viewBox="0 0 24 24" boxSize={4}>
      <path
        fill="currentColor"
        d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Zm17.71-10.04a.996.996 0 0 0 0-1.41l-2.5-2.5a.996.996 0 0 0-1.41 0l-1.96 1.96 3.75 3.75 1.92-1.8Z"
      />
    </Icon>
  );
}

export function ServingsStepper({
  currentServings,
  originalServings,
  isSaving = false,
  onDecrement,
  onIncrement,
  onSaveDefault,
}: ServingsStepperProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftServings, setDraftServings] = useState(String(originalServings));

  const saveDefault = async () => {
    const parsed = Number(draftServings);
    if (!Number.isInteger(parsed) || parsed < 1 || !onSaveDefault) {
      return;
    }

    await onSaveDefault(parsed);
    setIsEditing(false);
  };

  return (
    <HStack className="servingsStepper" spacing={3} wrap="wrap">
      <div className="servingsStepper__group" role="group">
        <button
          type="button"
          className="servingsStepper__step"
          aria-label="Decrease servings"
          onClick={onDecrement}
          disabled={currentServings <= 1}
        >
          −
        </button>
        <span className="servingsStepper__count" aria-live="polite">
          {currentServings} serving{currentServings === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          className="servingsStepper__step"
          aria-label="Increase servings"
          onClick={onIncrement}
        >
          +
        </button>
      </div>

      <Text color="gray.600" fontSize="sm">
        Base: {originalServings}
      </Text>

      {onSaveDefault ? (
        isEditing ? (
          <HStack spacing={2}>
            <Input
              size="sm"
              type="number"
              min={1}
              value={draftServings}
              onChange={(event) => setDraftServings(event.target.value)}
              className="servingsStepper__input"
            />
            <Button size="sm" onClick={saveDefault} isLoading={isSaving}>
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setIsEditing(false)}
              isDisabled={isSaving}
            >
              Cancel
            </Button>
          </HStack>
        ) : (
          <Tooltip label="Edit default servings" hasArrow>
            <button
              type="button"
              className="servingsStepper__edit"
              aria-label="Edit default servings"
              onClick={() => {
                setDraftServings(String(originalServings));
                setIsEditing(true);
              }}
            >
              <PencilIcon />
            </button>
          </Tooltip>
        )
      ) : null}
    </HStack>
  );
}
