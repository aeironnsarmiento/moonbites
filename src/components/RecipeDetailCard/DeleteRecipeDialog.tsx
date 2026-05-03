import {
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Button,
} from "@chakra-ui/react";
import { useRef } from "react";

type DeleteRecipeDialogProps = {
  isOpen: boolean;
  isDeleting: boolean;
  onClose: () => void;
  onDelete: () => void;
};

export function DeleteRecipeDialog({
  isOpen,
  isDeleting,
  onClose,
  onDelete,
}: DeleteRecipeDialogProps) {
  const cancelDeleteRef = useRef<HTMLButtonElement | null>(null);

  return (
    <AlertDialog
      isOpen={isOpen}
      leastDestructiveRef={cancelDeleteRef}
      onClose={onClose}
      isCentered
    >
      <AlertDialogOverlay>
        <AlertDialogContent>
          <AlertDialogHeader>Delete saved recipe?</AlertDialogHeader>
          <AlertDialogBody>
            This removes the entire saved recipe record, including overrides and favorite state.
          </AlertDialogBody>
          <AlertDialogFooter>
            <Button
              ref={cancelDeleteRef}
              variant="ghost"
              onClick={onClose}
              isDisabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              colorScheme="red"
              ml={3}
              onClick={onDelete}
              isLoading={isDeleting}
            >
              Delete recipe
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialogOverlay>
    </AlertDialog>
  );
}
