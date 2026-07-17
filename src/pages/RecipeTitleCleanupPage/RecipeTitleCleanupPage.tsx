import { useState } from "react";
import {
  Badge,
  Box,
  Button,
  Card,
  CardBody,
  Heading,
  HStack,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";

import { StatusBanner } from "../../components/StatusBanner/StatusBanner";
import { useTitleCleanup } from "../../hooks/useTitleCleanup";
import type { ApplyTitleItem, TitleSuggestion } from "../../types/recipe";
import "./RecipeTitleCleanupPage.scss";

type RowState = {
  title: string;
  rejected: boolean;
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function RecipeTitleCleanupPage() {
  const {
    preview,
    isPreviewing,
    previewError,
    loadPreview,
    isApplying,
    applyError,
    applyTitles,
  } = useTitleCleanup();

  const [rows, setRows] = useState<Record<string, RowState>>({});
  const [appliedCount, setAppliedCount] = useState<number | null>(null);

  const suggestions = preview?.suggestions ?? [];
  const skipped = preview?.skipped ?? [];

  // A row with no explicit state is accepted with the suggestion as-is, so
  // "accept the rest" is the no-op rather than something the user must click.
  const rowFor = (suggestion: TitleSuggestion): RowState =>
    rows[suggestion.recipeImportId] ?? {
      title: suggestion.suggestedTitle,
      rejected: false,
    };

  const handleLoad = async (nextCursor: string | null) => {
    setAppliedCount(null);
    setRows({});
    await loadPreview(nextCursor);
  };

  const keptItems = (): ApplyTitleItem[] =>
    suggestions
      .map((suggestion) => ({ suggestion, row: rowFor(suggestion) }))
      .filter(({ row }) => !row.rejected && row.title.trim().length > 0)
      .map(({ suggestion, row }) => ({
        recipeImportId: suggestion.recipeImportId,
        title: row.title.trim(),
      }));

  const handleApply = async () => {
    const items = keptItems();
    if (items.length === 0) {
      return;
    }
    const result = await applyTitles(items);
    setAppliedCount(result.appliedCount);
  };

  const keptCount = keptItems().length;

  return (
    <Stack spacing={8} className="titleCleanupPage">
      <Stack spacing={2}>
        <Text color="brand.600" fontWeight="700" fontSize="sm">
          Admin
        </Text>
        <Heading size="xl">Clean up recipe titles</Heading>
        <Text color="gray.600">
          Suggests clearer titles for recipes you haven&apos;t titled yourself.
          The original source title is always kept for attribution. Nothing
          changes until you apply.
        </Text>
      </Stack>

      {previewError ? (
        <StatusBanner
          error={errorMessage(previewError, "Unable to load suggestions.")}
        />
      ) : null}
      {applyError ? (
        <StatusBanner
          error={errorMessage(applyError, "Unable to apply titles.")}
        />
      ) : null}
      {appliedCount !== null ? (
        <StatusBanner
          status={`Applied ${appliedCount} ${appliedCount === 1 ? "title" : "titles"}.`}
        />
      ) : null}
      {preview?.degradedReason ? (
        <Text color="orange.600" fontSize="sm">
          The title generator degraded, so these are cleaned-up source titles
          rather than AI suggestions. {preview.degradedReason}
        </Text>
      ) : null}

      <HStack spacing={3}>
        <Button
          colorScheme="brand"
          onClick={() => handleLoad(null)}
          isLoading={isPreviewing}
        >
          {preview ? "Reload suggestions" : "Load suggestions"}
        </Button>
        {preview?.nextCursor ? (
          <Button
            variant="outline"
            colorScheme="brand"
            onClick={() => handleLoad(preview.nextCursor)}
            isLoading={isPreviewing}
          >
            Load next batch
          </Button>
        ) : null}
      </HStack>

      {preview && suggestions.length === 0 && skipped.length === 0 ? (
        <Text color="gray.500">
          No recipes need a new title right now.
        </Text>
      ) : null}

      {suggestions.length > 0 ? (
        <Stack spacing={4}>
          {suggestions.map((suggestion) => {
            const row = rowFor(suggestion);
            const rejected = row.rejected;

            return (
              <Card
                key={suggestion.recipeImportId}
                className={
                  rejected
                    ? "titleCleanupPage__row titleCleanupPage__row--rejected"
                    : "titleCleanupPage__row"
                }
              >
                <CardBody>
                  <Stack spacing={3}>
                    <HStack justify="space-between" wrap="wrap" spacing={3}>
                      <Text color="gray.500" fontSize="sm">
                        Currently: {suggestion.currentTitle}
                      </Text>
                      {suggestion.source === "fallback" ? (
                        <Badge colorScheme="orange">
                          cleaned source title — no confident AI suggestion
                        </Badge>
                      ) : null}
                    </HStack>

                    <HStack spacing={3} align="center">
                      <Input
                        aria-label={`New title for ${suggestion.currentTitle}`}
                        value={row.title}
                        isDisabled={rejected}
                        onChange={(event) =>
                          setRows((current) => ({
                            ...current,
                            [suggestion.recipeImportId]: {
                              ...row,
                              title: event.target.value,
                            },
                          }))
                        }
                      />
                      <Button
                        variant={rejected ? "solid" : "outline"}
                        colorScheme={rejected ? "gray" : "brand"}
                        onClick={() =>
                          setRows((current) => ({
                            ...current,
                            [suggestion.recipeImportId]: {
                              ...row,
                              rejected: !rejected,
                            },
                          }))
                        }
                      >
                        {rejected ? "Rejected" : "Reject"}
                      </Button>
                    </HStack>

                    {suggestion.reason ? (
                      <Text color="gray.500" fontSize="xs">
                        {suggestion.reason}
                      </Text>
                    ) : null}
                  </Stack>
                </CardBody>
              </Card>
            );
          })}

          <Box>
            <Button
              colorScheme="brand"
              onClick={handleApply}
              isLoading={isApplying}
              isDisabled={keptCount === 0}
            >
              Apply {keptCount} {keptCount === 1 ? "title" : "titles"}
            </Button>
          </Box>
        </Stack>
      ) : null}

      {skipped.length > 0 ? (
        <Stack spacing={2} className="titleCleanupPage__skipped">
          <Heading size="sm" color="gray.600">
            Skipped ({skipped.length})
          </Heading>
          {skipped.map((item) => (
            <Text key={item.recipeImportId} color="gray.500" fontSize="sm">
              {item.currentTitle} — {item.reason}
            </Text>
          ))}
        </Stack>
      ) : null}
    </Stack>
  );
}
