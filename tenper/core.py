#!/usr/bin/env python
"""Tenper is a tmux wrapper with support for Python virtualenv.

The name is a corruption of gibberish:
    tmuxvirtualenvwrapper -> tenvpapper -> tenper.

Environment variables:
    TENPER_CONFIGS: The path to where you want the configuration files stored.
        Defaults to ~/.tenper.
    TENPER_VIRTUALENVS: The path to where you keep your virtualenvs. Defaults
        to virtualenvwrapper's default of ~/.virtualenvs.
    TENPER_TMUX_COMMAND: Defaults to 'tmux'.
"""

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys

import yaml

from . import command
from . import config


_run_context = {
    'editor': os.getenv('EDITOR'),
    'config_path': os.getenv('TENPER_CONFIGS') or \
        os.path.join(os.path.expanduser('~'), '.tenper'),
    'virtualenvs_path': os.getenv('TENPER_VIRTUALENVS') or \
        os.path.join(os.path.expanduser('~'), '.virtualenvs'),
    'tmux_command': os.getenv('TENPER_TMUX_COMMAND') or 'tmux',

    # These are the YAML config properties we'll want to use in the subprocess
    # calls.
    'config_file_name': None,
    'project_root': None,
    'session_name': None,
    'virtualenv_configured': False,
    'virtualenv_path': None,
    'virtualenv_python_binary': None,
    'virtualenv_use_site_packages': '--no-site-packages',

    # TODO(mason): Am I confounding two things here? The following are stored
    # from the config and used as part of the program logic, not simple
    # replacements applied to the subprocess calls. This is convenient, but I'm
    # unsure.
    'environment': {},
    'windows': [],
}


@contextlib.contextmanager
def run_context(**kwargs):
    """Updates the global run context safely."""

    global _run_context

    old_run_context = _run_context
    _run_context = old_run_context.copy()
    _run_context.update(**kwargs)
    yield _run_context
    _run_context = old_run_context


def configured(string):
    """Returns 'string' formatted with the run context."""
    return string.format(**_run_context)


def run(command, **kwargs):
    """Runs a command. The command is formatted with the run_context.

    This permits the following usage. The run context is augmented with
    temporary parameters. We no longer need to execute string.format for every
    parameterized command. It's more legible.

        with run_context(temporary_thing='foobar'):
            run('cp {temporary_thing} {config_path}')

    Args:
        command: A string with spaces. It'll be split on spaces and then be
            formatted with the run_context and kwargs.
        kwargs: Additional formatting.

    Returns:
        A boolean indicating success and the command output: (ok, output).
    """

    formatting = dict(list(_run_context.items()) + list(kwargs.items()))

    print('* {}'.format(command.format(**formatting)))

    try:
        output = subprocess.check_output(
            [part.format(**formatting) for part in command.split(' ')])
        ok = True
    except subprocess.CalledProcessError as e:
        output = e.output
        ok = False

    return (ok, output.decode())


def parse_args(args):
    """Handles user input.

    Args:
        args: Probably never anything but sys.argv[1:].

    Returns:
        A Namespace with 'command' and/or 'project_name' properties.
    """

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            'A wrapper for tmux sessions and (optionally) virtualenv.\n\n'
            'Usage:\n'
            '    tenper list\n'
            '    tenper edit my-project\n'
            '    tenper rebuild my-project\n'
            '    tenper delete my-project\n'
            '    tenper my-project\n'))

    if len(args) == 1:
        # Either 'list' or a project name.
        parser.add_argument('project_name')
        parser.set_defaults(command='start')

    else:
        # Subcommand.
        subparsers = parser.add_subparsers(dest='command')

        def mksubparser(name, help_text):
            sp = subparsers.add_parser(name, help=help_text)
            sp.add_argument('project_name')

        mksubparser('edit', 'Edit a project\'s configuration.')
        mksubparser('rebuild', 'Delete an existing virtualenv and start a new one.')
        mksubparser('delete', 'Delete a project\'s virtualenv and configuration.')

    parsed_args = parser.parse_args(args)

    # meh.
    if parsed_args.project_name == 'list':
        parsed_args.command = 'list'
        del parsed_args.project_name

    return parsed_args


def user_input(prompt):
    """Returns user input in Python 2 or 3."""

    try:
        return raw_input(prompt)
    except (EOFError, NameError, ValueError):
        return input(prompt)


def main(*args, **kwargs):
    arguments = parse_args(sys.argv[1:])

    if arguments.command == 'list':
        command.list()

    else:
        config_file_name = os.path.join(_run_context['config_path'],
                                        '{}.yml'.format(arguments.project_name))

        with run_context(**config.load(config_file_name)):
            getattr(command, arguments.command)(arguments.project_name)
