FROM nginx:latest

COPY nginx.dev.conf /etc/nginx/nginx.conf

CMD ["nginx", "-g", "daemon off;"]
