import React, { Fragment } from 'react';
import { Blockquote, Code, Divider, List, Text, Title } from '@mantine/core';

const TOKEN_PATTERN = /(\[(?:\/)?(?:b|i|u|h1|h2|h3|quote|code|list|hr|\*|url(?:=[^\]\r\n]*)?)\])/gi;
const TAG_PATTERN = /^\[(\/)?([a-z0-9*]+)(?:=([^\]\r\n]*))?\]$/i;

const safeExternalHref = (candidate) => {
  try {
    const url = new URL(candidate.trim());
    return ['http:', 'https:', 'mailto:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
};

const renderContainer = (tag, children, key, href) => {
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
  if (tag === 'url' && href) {
    return <a href={href} key={key} target="_blank" rel="noopener noreferrer">{children}</a>;
  }
  return <Fragment key={key}>{children}</Fragment>;
};

const parseTokens = (bbcode) => {
  const root = { tag: 'root', children: [] };
  const stack = [root];
  const closeTop = (key) => {
    const node = stack.pop();
    const href = node.tag === 'url' ? safeExternalHref(node.href ?? node.text) : undefined;
    stack.at(-1).children.push(renderContainer(node.tag, node.children, key, href));
  };

  bbcode.split(TOKEN_PATTERN).filter(Boolean).forEach((token, index) => {
    const match = token.match(TAG_PATTERN);
    if (!match) {
      stack.at(-1).children.push(<Fragment key={`text-${index}`}>{token}</Fragment>);
      stack.forEach((node) => {
        node.text = `${node.text ?? ''}${token}`;
      });
      return;
    }
    const [, closing, rawTag, rawValue] = match;
    const tag = rawTag.toLowerCase();
    if (tag === 'hr' && !closing) {
      stack.at(-1).children.push(<Divider key={`hr-${index}`} my="sm" />);
      return;
    }
    if (closing) {
      if (tag === 'list' && stack.at(-1).tag === '*') closeTop(`implicit-item-${index}`);
      if (stack.length === 1 || stack.at(-1).tag !== tag) {
        stack.at(-1).children.push(<Fragment key={`text-${index}`}>{token}</Fragment>);
        return;
      }
      closeTop(`tag-${index}`);
      return;
    }
    if (tag === '*' && stack.at(-1).tag === '*') closeTop(`implicit-item-${index}`);
    stack.push({ tag, children: [], href: tag === 'url' ? rawValue : undefined, text: '' });
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
