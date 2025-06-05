set -eo pipefail

COLOR_GREEN=`tput setaf 2;`
COLOR_BLUE=`tput setaf 4;`
COLOR_NC=`tput sgr0;` # No Color

cd "$(dirname "$0")/../.."

echo "${COLOR_BLUE}Starting black${COLOR_NC}"
poetry run black .
echo "OK"

echo "${COLOR_BLUE}Starting isort${COLOR_NC}"
poetry run Isort .
echo "OK"

echo "${COLOR_GREEN}Code Formatting successfully!${COLOR_NC}"
