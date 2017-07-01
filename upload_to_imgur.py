"""
Helps uploading the images in this repository to imgur using their OAuth2 API https://apidocs.imgur.com/

The configuration should be put into imgur.ini which should be of the form
    [DEFAULT]
    user = <user on imgur to be used for creating albums and uploading pix>

    [client]
    id = <your imgur app ID>
    secret = <your imgur app secret>

    [tokens]
    access = <actually optional>
    refresh = <keep this in order to get a new access token each time the script is launched>

# On Imgur

All titles on imgur will be relative to the lnxpcs directory

Album titles will be the full path to the image directory
Picture titles will be the full path to the image
"""
import argparse
import os
from configparser import ConfigParser

from imgurpython.helpers.error import ImgurClientRateLimitError
from imgurpython import ImgurClient

REPO_DIR = "lnxpcs"
CONFIG_FILENAME = "imgur.ini"
CLIENT_SECTION = "client"
TOKENS_SECTION = "tokens"

ROOT_URL = "https://github.com/jstpcs/"


def request_new_token(config, client_id, client_secret):
    """
    :type config: ConfigParser
    :type client_id: str
    :type client_secret: str
    """
    client = ImgurClient(client_id, client_secret)
    authorization_url = client.get_auth_url('pin')

    pin = input("Please enter the pin you received from %s\n" % authorization_url)

    credentials = client.authorize(pin, 'pin')
    config.set(TOKENS_SECTION, "access", credentials["access_token"])
    config.set(TOKENS_SECTION, "refresh", credentials["refresh_token"])
    with open(CONFIG_FILENAME, "w") as config_file:
        config.write(config_file)
    print("Updated config for future use")


def find_all_images(root_dir):
    """
    :param root_dir: Directory containing the repo
    :type root_dir: str
    :return: album titles and files they should include
    :rtype: list[tuple(str,str)]
    """
    images = []
    for walk_root, dirs, files in os.walk(os.path.join(root_dir, REPO_DIR)):
        pngs = [file for file in files if file.endswith(".png")]
        if pngs:
            images.append((os.path.relpath(walk_root, root_dir), pngs))
    return images


def get_album(client, all_albums, title, album_url):
    """

    :param client:
    :type client: ImgurClient
    :param all_albums:
    :type all_albums: dict
    :param title:
    :type title: str
    :param album_url:
    :type album_url:
    :return:
    :rtype:
    """
    if title in all_albums:
        return all_albums[title]
    album = client.get_album(client.create_album({
        "title": title,
        "privacy": "hidden",
        "description": "Album of images from %s" % album_url
    })["id"])
    all_albums[title] = album
    return album


def get_album_image(album, file_path):
    return next(iter([image for image in album.images if image["title"] == file_path]), None)


def main(config, path_to_repo):
    # Note since access tokens expire after an hour, only the refresh token is required (library handles autorefresh)
    client = ImgurClient(
        config.get(CLIENT_SECTION, "id"),
        config.get(CLIENT_SECTION, "secret"),
        config.get(TOKENS_SECTION, "access"),
        config.get(TOKENS_SECTION, "refresh")
    )

    if os.path.basename(path_to_repo) != REPO_DIR:
        print("Please provide a path to a lnxpcs directory. Given %s" % path_to_repo)
        exit(1)
    elif not os.path.isdir(path_to_repo):
        print("Please provide a path to an EXISTING lnxpcs directory. Given %s" % path_to_repo)
        exit(1)

    path_to_repo_parent = os.path.realpath(os.path.join(path_to_repo, ".."))

    images = find_all_images(path_to_repo_parent)
    all_albums = {
        album.title: client.get_album(album.id)  # Get the full albums and its list of images
        for album in client.get_account_albums(config.get("DEFAULT", "user"))
    }

    try:
        for album_imgur_title, pngs in images:
            album_git_url = "%s%s" % (ROOT_URL, album_imgur_title.replace(REPO_DIR, "lnxpcs/tree/master"))
            album = get_album(client, all_albums, album_imgur_title, album_git_url)
            print("Handling album %s" % album_git_url)
            print("Album @ %s" % album.link)
            for png in pngs:
                image_file_path = os.path.join(path_to_repo_parent, album_imgur_title, png)
                image_rel_path = os.path.join(album_imgur_title, png)
                image_git_url = "%s/%s" % (album_git_url, png)
                print("\tHandling image %s" % image_git_url)
                album_image = get_album_image(album, image_rel_path)
                if album_image:
                    # TODO check if the current image is newer
                    pass
                else:
                    album_image = client.upload_from_path(image_file_path, {
                        "title": image_rel_path,
                        "description": "A mirror of %s" % image_git_url,
                        "album": album.deletehash
                    })
                    print("\t\tUploaded to %s" % album_image["link"])
    except ImgurClientRateLimitError as rle:
        print("Passed limit", client.credits)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="A helper to upload all images in the repo to imgur"
    )
    parser.add_argument(
        "-d", "--repo_dir",
        help="A path to the repository containing all the sweet sweet linux images",
        default=os.path.abspath(os.path.curdir),
        required=False
    )

    args = parser.parse_args()

    # If you already have an access/refresh pair in hand
    config = ConfigParser()
    config.read(CONFIG_FILENAME)

    if CLIENT_SECTION not in config:
        print("You need a client configuration to access imgur. Get one at https://apidocs.imgur.com/")
        exit(1)
    client_config = config[CLIENT_SECTION]
    if "id" not in client_config or "secret" not in client_config:
        print("Client config incomplete!")
        exit(1)

    try:
        imgur_user = config.get("DEFAULT", "user")
    except:
        print("Please add an imgur user to the default section of the configuration")
        exit(1)

    if TOKENS_SECTION in config and "refresh" in config[TOKENS_SECTION] and "access" in config[TOKENS_SECTION]:
        main(config, args.repo_dir)
    else:
        if TOKENS_SECTION not in config:
            config.add_section(TOKENS_SECTION)
        request_new_token(config, client_config["id"], client_config["secret"])
        main(config, args.repo_dir)
