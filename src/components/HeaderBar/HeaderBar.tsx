import { Box, Button, Flex, Heading, HStack, Text } from "@chakra-ui/react";
import { NavLink, Link } from "react-router-dom";

import "./HeaderBar.scss";

const navItems = [
  { label: "Home", to: "/" },
  { label: "Recipe List", to: "/recipes" },
];

export function HeaderBar() {
  return (
    <Box as="header" className="headerBar">
      <Flex align="center" justify="space-between" className="headerBar__inner">
        <Box as={Link} to="/" style={{ textDecoration: "none" }}>
          <Text className="headerBar__eyebrow">Moonlake Cookbook</Text>
          <Heading size="md">Moonbites</Heading>
        </Box>

        <HStack spacing={3}>
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"}>
              {({ isActive }) => (
                <Button
                  variant={isActive ? "solid" : "ghost"}
                  className="headerBar__navButton"
                >
                  {item.label}
                </Button>
              )}
            </NavLink>
          ))}
        </HStack>
      </Flex>
    </Box>
  );
}
