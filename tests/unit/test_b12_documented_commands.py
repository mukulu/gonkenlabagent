"""Executable README catalogue and native-SVG current-architecture checks."""
from __future__ import annotations
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from gonken_agent.cli import _build_parser
from gonken_agent.environment.intents import parse_environment_intent, EnvironmentIntent
from gonken_agent.command_intents import parse_command, CommandIntent, CommandClarification
from gonken_agent.power import power_intent
from gonken_agent.tool_broker import direct_clock_intent

ROOT=Path(__file__).resolve().parents[2]

class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.catalog=json.loads((ROOT/'docs/COMMAND_EXAMPLES.json').read_text())

    def test_every_terminal_example_parses_without_execution(self):
        parser=_build_parser()
        for row in self.catalog['terminal']:
            with self.subTest(command=row['command']):
                value=parser.parse_args(row['args'])
                self.assertIsNotNone(value.command)

    def test_every_voice_example_maps_to_documented_operation_and_arguments(self):
        for row in self.catalog['voice']:
            with self.subTest(text=row['text']):
                if row['parser']=='clock': self.assertIsNotNone(direct_clock_intent(row['text']));continue
                if row['parser']=='power': self.assertEqual(power_intent(row['text']),row['operation']);continue
                result=(parse_environment_intent if row['parser']=='environment' else parse_command)(row['text'])
                self.assertIsInstance(result,(EnvironmentIntent,CommandIntent))
                self.assertEqual(result.operation,row['operation'])
                for key,value in row['params'].items():
                    if key=='response_kind':self.assertEqual(result.response_kind,value)
                    else:self.assertEqual(result.params[key],value)

    def test_catalogue_is_visible_in_root_readme_not_buried(self):
        readme=(ROOT/'README.md').read_text()
        for row in self.catalog['voice']: self.assertIn(row['text'],readme)
        for row in self.catalog['terminal']:
            # Only explicit sudo/service-identity prefixes differ in display.
            self.assertIn(row['command'],readme)
        self.assertIn('docs/ARCHITECTURE.md',readme)
        self.assertIn('28 C',readme);self.assertIn('26 C',readme)
        self.assertIn('qwen3:0.6b',readme)

    def test_current_document_local_links_exist(self):
        for relative in ['README.md','PRD.md','docs/ARCHITECTURE.md','docs/ROOM_APPLIANCE_INSTALL.md']:
            file=ROOT/relative
            for destination in re.findall(r'\]\(([^)\s]+)\)',file.read_text()):
                if destination.startswith(('https://','http://','#','mailto:')):continue
                path=destination.split('#')[0]
                with self.subTest(file=relative,destination=destination):self.assertTrue((file.parent/path).is_file())

    def test_svg_architecture_is_native_accessible_and_passive(self):
        paths=sorted((ROOT/'docs/diagrams').glob('*.svg'));self.assertEqual(len(paths),3)
        for path in paths:
            root=ET.parse(path).getroot();self.assertEqual(root.attrib.get('role'),'img')
            tags={node.tag.split('}')[-1] for node in root.iter()}
            self.assertIn('title',tags);self.assertIn('desc',tags);self.assertIn('text',tags)
            self.assertFalse({'script','foreignObject','image','animate','set'} & tags)
            for node in root.iter():
                for key,value in node.attrib.items():
                    self.assertFalse(key.lower().startswith('on'))
                    if key.endswith('href'):self.assertTrue(value.startswith('#'))

    def test_ambiguous_new_requirements_are_not_silently_acted_on(self):
        for text in ['tell me when temperature increases by two minutes',
                     'turn the fan on after minutes',
                     'turn the fan on in two minutes and stop after three minutes']:
            with self.subTest(text=text):self.assertIsInstance(parse_command(text),CommandClarification)

    def test_conceptual_sensor_questions_reach_conversation_not_live_reading(self):
        for text in ["Why does humidity change?", "What is humidity?", "Explain photosynthesis in one sentence"]:
            with self.subTest(text=text):
                self.assertIsNone(parse_command(text))
                self.assertIsNone(parse_environment_intent(text))
                self.assertIsNone(power_intent(text))

    def test_future_display_not_presented_as_shipped_command(self):
        readme=(ROOT/'README.md').read_text()
        self.assertIn('does not\nprovide `gonken-agent console`',readme)
        self.assertIn('planned, not shipped', (ROOT/'docs/ARCHITECTURE.md').read_text().lower())
