import React, { Fragment } from 'react';
import { Blockquote, Code, List, Text, Title } from '@mantine/core';

const TOKEN_PATTERN = /(\[(?:\/)?(?:b|i|u|h1|h2|h3|quote|code|list|\*)\])/gi;
const TAG_PATTERN = /^\[(\/)?([a-z0-9*]+)\]$/i;

const renderContainer = (tag, children, key) => {
  if (tag === 'b') return <Text span fw={700} key={key}>{children}</Text>;
  if (tag === 'i') return <Text span fs="italic" key={key}>{children}</Text>;
  if (tag === 'u') return <Text span td="underline" key={key}>{children}</Text>;
  if (tag === 'h1') return <Title order={2} key={key}>{children}</Title>;
  if (tag === 'h2') return <Title order={3} key={key}>{children}</Title>;
  if (tag === 'h3') return <Title order={4} key={key}>{children}</Title>;
  if (tag === 'quote') return <Blockquote key={key}>{children}</Blockquote>;
  if (tag === 'code') return <Code block key={key}>{children}</Code>;
  if (tag === 'list') return <List key={key}>{children}</List>;
  if (tag === '*') return <List.Item key={key}>{children}</List.Item>;
  return <Fragment key={key}>{children}</Fragment>;
};

const parseTokens = (bbcode) => {
  const root = { tag: 'root', children: [] };
  const stack = [root];

  bbcode.split(TOKEN_PATTERN).filter(Boolean).forEach((token, index) => {
    const match = token.match(TAG_PATTERN);
    if (!match) {
      stack.at(-1).children.push(<Fragment key={`text-${index}`}>{token}</Fragment>);
      return;
    }
    const [, closing, rawTag] = match;
    const tag = rawTag.toLowerCase();
    if (closing) {
      if (stack.length === 1 || stack.at(-1).tag !== tag) {
        stack.at(-1).children.push(<Fragment key={`text-${index}`}>{token}</Fragment>);
        return;
      }
      const node = stack.pop();
      stack.at(-1).children.push(renderContainer(node.tag, node.children, `tag-${index}`));
      return;
    }
    stack.push({ tag, children: [] });
  });

  while (stack.length > 1) {
    const node = stack.pop();
    stack.at(-1).children.push(
      <Fragment key={`open-${stack.length}-${node.tag}`}>[{node.tag}]</Fragment>,
      ...node.children,
    );
  }
  return root.children;
};

export const BbcodePreview = ({ bbcode }) => (
  <div
    aria-label="BBCode 预览"
    data-remis-surface="paper"
    style={{
      background: 'var(--paper-bg)',
      border: '1px solid var(--surface-border)',
      borderRadius: 'var(--mantine-radius-md)',
      minHeight: 180,
      padding: 16,
      whiteSpace: 'pre-wrap',
      overflowWrap: 'anywhere',
      color: 'var(--remis-content-text, var(--paper-text-main))',
    }}
  >
    {bbcode ? parseTokens(bbcode) : <Text c="dimmed">输入 BBCode 后在这里预览。</Text>}
  </div>
);
