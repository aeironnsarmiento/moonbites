import {
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
  Badge,
  Box,
  Divider,
  Flex,
  Heading,
  HStack,
  Stack,
  Text,
} from "@chakra-ui/react";

import {
  buildNutritionFacts,
  isBatchScalable,
  scaleNutritionEntry,
  type NutritionFactEntry,
} from "../../utils/nutritionFacts";

type NutritionFactsPanelProps = {
  nutrition: Record<string, string> | null;
  recordServings: number | null;
  currentServings: number;
};

type NutritionRowProps = {
  label: string;
  value: string;
  emphasize?: boolean;
};

function NutritionRow({ label, value, emphasize = false }: NutritionRowProps) {
  return (
    <Flex
      justify="space-between"
      align="baseline"
      gap={3}
      py={1}
      borderBottom="1px solid"
      borderColor="blackAlpha.200"
      fontSize={emphasize ? "md" : "sm"}
    >
      <Text as="dt" fontWeight={emphasize ? "700" : "600"}>
        {label}
      </Text>
      <Text as="dd" m={0} textAlign="right">
        {value}
      </Text>
    </Flex>
  );
}

export function NutritionFactsPanel({
  nutrition,
  recordServings,
  currentServings,
}: NutritionFactsPanelProps) {
  const facts = buildNutritionFacts(nutrition, recordServings);

  if (!facts) {
    return (
      <Stack spacing={3} className="recipeDetailCard__section">
        <Heading size="sm">Nutrition</Heading>
        <Text fontSize="sm" color="gray.600">
          The source did not provide nutrition information.
        </Text>
      </Stack>
    );
  }

  const batchEntries = facts.entries.filter(isBatchScalable);
  const showBatchView =
    facts.perServing &&
    batchEntries.length > 0 &&
    Number.isFinite(currentServings) &&
    currentServings > 0;

  return (
    <Stack spacing={3} className="recipeDetailCard__section">
      <HStack justify="space-between" wrap="wrap" spacing={3}>
        <Heading size="sm">Nutrition</Heading>
        <Text fontSize="sm" color="gray.600">
          {facts.perServing ? "Per serving" : "As provided by the source"}
        </Text>
      </HStack>

      {facts.servingSize ? (
        <Text fontSize="sm" color="gray.600">
          Serving size: {facts.servingSize}
        </Text>
      ) : null}

      <Divider borderColor="blackAlpha.400" borderBottomWidth="3px" />

      <Box as="dl" m={0}>
        {facts.entries.map((entry: NutritionFactEntry) => (
          <NutritionRow
            key={entry.id}
            label={entry.label}
            value={entry.display}
            emphasize={entry.id === "calories"}
          />
        ))}
      </Box>

      {showBatchView ? (
        <Accordion allowToggle>
          <AccordionItem border="none">
            <AccordionButton px={0} _hover={{ background: "transparent" }}>
              <HStack flex="1" textAlign="left" spacing={2}>
                <Text fontSize="sm" fontWeight="600">
                  Batch totals for {currentServings}{" "}
                  {currentServings === 1 ? "serving" : "servings"}
                </Text>
                <Badge colorScheme="brand" fontSize="0.65rem">
                  Calculated
                </Badge>
              </HStack>
              <AccordionIcon />
            </AccordionButton>
            <AccordionPanel px={0} pb={2}>
              <Box as="dl" m={0}>
                {batchEntries.map((entry) => (
                  <NutritionRow
                    key={`batch-${entry.id}`}
                    label={entry.label}
                    value={scaleNutritionEntry(entry, currentServings)}
                    emphasize={entry.id === "calories"}
                  />
                ))}
              </Box>
              <Text fontSize="xs" color="gray.600" mt={2}>
                Calculated from per-serving values for {currentServings}{" "}
                {currentServings === 1 ? "serving" : "servings"}. Source-provided
                values are per serving.
              </Text>
            </AccordionPanel>
          </AccordionItem>
        </Accordion>
      ) : null}
    </Stack>
  );
}
