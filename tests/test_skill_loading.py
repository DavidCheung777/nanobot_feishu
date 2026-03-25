import os
import unittest


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILLS_DIR = os.path.join(BASE_DIR, "feishu", "skills")


def _extract_front_matter(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx]
    return None


def _parse_name_and_description(lines):
    name = None
    description = None
    in_description = False
    buf = []
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("name:"):
            name = stripped.split(":", 1)[1].strip()
            in_description = False
            continue
        if stripped.startswith("description:"):
            if stripped.endswith("|"):
                in_description = True
                buf = []
            else:
                description = stripped.split(":", 1)[1].strip()
                in_description = False
            continue
        if in_description:
            if stripped.startswith(" "):
                buf.append(stripped.lstrip())
            else:
                in_description = False
                if buf:
                    description = "\n".join(buf).strip()
    if in_description and buf:
        description = "\n".join(buf).strip()
    return name, description


class TestSkillLoading(unittest.TestCase):
    def test_skills_directory_exists(self):
        self.assertTrue(os.path.isdir(SKILLS_DIR))

    def test_skill_front_matter(self):
        skills = [
            "feishu-bitable",
            "feishu-calendar",
            "feishu-channel-rules",
            "feishu-create-doc",
            "feishu-fetch-doc",
            "feishu-im-read",
            "feishu-task",
            "feishu-troubleshoot",
            "feishu-update-doc",
        ]
        for skill in skills:
            skill_path = os.path.join(SKILLS_DIR, skill, "SKILL.md")
            self.assertTrue(os.path.isfile(skill_path), msg=f"缺少 {skill_path}")
            with open(skill_path, "r", encoding="utf-8") as f:
                text = f.read()
            front_matter = _extract_front_matter(text)
            self.assertIsNotNone(front_matter, msg=f"{skill} 缺少 YAML 前置块")
            name, description = _parse_name_and_description(front_matter)
            self.assertTrue(name, msg=f"{skill} 缺少 name")
            self.assertTrue(description, msg=f"{skill} 缺少 description")
