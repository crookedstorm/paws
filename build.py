#!/usr/bin/python3
import os
import argparse
import subprocess


def last_git_modified(path):
    return subprocess.check_output([
        'git',
        'log',
        '-n', '1',
        '--pretty=format:%h',
        path
    ]).decode('utf-8')

def image_touched(image, commit_range):
    return subprocess.check_output([
        'git', 'diff', '--name-only', commit_range, os.path.join('images', image)
    ]).decode('utf-8').strip() != ''

def build_images(prefix, images, commit_range=None, push=False):
    for image in images:
        if commit_range:
            if not image_touched(image, commit_range):
                print("Skipping {}, not touched in {}".format(image, commit_range))
                continue
        image_path = os.path.join('images', image)
        tag = last_git_modified(image_path)
        image_spec = '{}{}:{}'.format(prefix, image, tag)

        subprocess.check_call([
            'docker', 'build', '-t', image_spec, image_path
        ])
        if push:
            subprocess.check_call([
                'docker', 'push', image_spec
            ])

def deploy(prefix, images, release, install):
    image_map = {
        'singleuser': 'jupyterhub.singleuser.image',
        'db-proxy': 'dbProxy.image',
        'query-killer': 'query-killer.image',
        'deploy-hook': 'deployHook.image'
    }

    args = []

    # Set up helm!
    subprocess.check_call(['helm', 'init', '--client-only'])
    subprocess.check_call(['helm', 'dep', 'up'], cwd='paws')

    for image in images:
        image_path = os.path.join('images', image)
        image_name = prefix + image
        tag = last_git_modified(image_path)
        args.append('--set={}.name={}'.format(image_map[image], image_name))
        args.append('--set={}.tag={}'.format(image_map[image], tag))



    if install:
        helm = [
            'helm', 'install',
            '--name', release,
            '--namespace', release,
            'paws/',
            '-f', 'paws/secrets.yaml'
        ]
    else:
        helm = [
            'helm', 'upgrade', release,
            'paws/',
            '-f', 'paws/secrets.yaml'
        ]

    subprocess.check_call(helm + args)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        '--image-prefix',
        default='quay.io/wikimedia-paws/'
    )
    subparsers = argparser.add_subparsers(dest='action')

    build_parser = subparsers.add_parser('build', description='Build & Push images')
    build_parser.add_argument('--commit-range', help='Range of commits to consider when building images')
    build_parser.add_argument('--push', action='store_true')

    deploy_parser = subparsers.add_parser('deploy', description='Deploy with helm')
    deploy_parser.add_argument('release', default='prod')
    deploy_parser.add_argument('--install', action='store_true')


    args = argparser.parse_args()

    images = ['singleuser', 'db-proxy', 'query-killer', 'deploy-hook']
    if args.action == 'build':
        build_images(args.image_prefix, images, args.commit_range, args.push)
    else:
        deploy(args.image_prefix, images, args.release, args.install)

main()
