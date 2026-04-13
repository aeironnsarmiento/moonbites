import { Button, ButtonGroup, HStack, Text } from "@chakra-ui/react";

import "./PaginationControls.scss";

type PaginationControlsProps = {
  page: number;
  totalPages: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  isDisabled?: boolean;
};

export function PaginationControls({
  page,
  totalPages,
  totalCount,
  onPageChange,
  isDisabled,
}: PaginationControlsProps) {
  return (
    <HStack justify="space-between" className="paginationControls">
      <Text color="gray.500">{totalCount} saved recipes</Text>

      <ButtonGroup isAttached>
        <Button
          variant="outline"
          onClick={() => onPageChange(page - 1)}
          isDisabled={page <= 1 || isDisabled}
        >
          Previous
        </Button>
        <Button variant="ghost" isDisabled>
          Page {page} / {totalPages}
        </Button>
        <Button
          variant="outline"
          onClick={() => onPageChange(page + 1)}
          isDisabled={page >= totalPages || isDisabled}
        >
          Next
        </Button>
      </ButtonGroup>
    </HStack>
  );
}
