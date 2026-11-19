from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .forms import CommentForm, PostForm, ProfileForm
from .models import Category, Comment, Post


def _published():
    return Q(
        is_published=True,
        category__is_published=True,
        pub_date__lte=timezone.now(),
    )


def _posts():
    return Post.objects.select_related('author', 'category', 'location')


def _page(request, posts):
    posts = posts.annotate(comment_count=Count('comments')).order_by(
        '-pub_date', '-pk'
    )
    return Paginator(posts, 10).get_page(request.GET.get('page'))


def _visible_post(request, post_id):
    visibility = _published()
    if request.user.is_authenticated:
        visibility |= Q(author=request.user)
    return get_object_or_404(_posts().filter(visibility), pk=post_id)


def _render_detail(request, post, form):
    return render(
        request,
        'blog/detail.html',
        {
            'post': post,
            'form': form,
            'comments': post.comments.select_related('author'),
        },
    )


def index(request):
    return render(
        request,
        'blog/index.html',
        {'page_obj': _page(request, _posts().filter(_published()))},
    )


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True
    )
    return render(
        request,
        'blog/category.html',
        {
            'category': category,
            'page_obj': _page(
                request, _posts().filter(_published(), category=category)
            ),
        },
    )


def profile(request, username):
    owner = get_object_or_404(get_user_model(), username=username)
    posts = _posts().filter(author=owner)
    if owner != request.user:
        posts = posts.filter(_published())
    return render(
        request,
        'blog/profile.html',
        {'profile': owner, 'page_obj': _page(request, posts)},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def edit_profile(request):
    form = ProfileForm(
        request.POST if request.method == 'POST' else None,
        instance=request.user,
    )
    if form.is_valid():
        owner = form.save()
        return redirect('blog:profile', username=owner.username)
    return render(request, 'blog/user.html', {'form': form})


def post_detail(request, post_id):
    return _render_detail(
        request, _visible_post(request, post_id), CommentForm()
    )


@login_required
@require_http_methods(['GET', 'POST'])
def create_post(request):
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES or None,
    )
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_post(request, post_id):
    post = _visible_post(request, post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES or None,
        instance=post,
    )
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def delete_post(request, post_id):
    post = _visible_post(request, post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:profile', username=request.user.username)
    return render(
        request, 'blog/create.html', {'form': PostForm(instance=post)}
    )


@login_required
@require_POST
def add_comment(request, post_id):
    post = _visible_post(request, post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        return redirect('blog:post_detail', post_id=post_id)
    return _render_detail(request, post, form)


@login_required
@require_http_methods(['GET', 'POST'])
def edit_comment(request, post_id, comment_id):
    post = _visible_post(request, post_id)
    comment = get_object_or_404(Comment, pk=comment_id, post=post)
    if comment.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    form = CommentForm(
        request.POST if request.method == 'POST' else None,
        instance=comment,
    )
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render(
        request, 'blog/comment.html', {'comment': comment, 'form': form}
    )


@login_required
@require_http_methods(['GET', 'POST'])
def delete_comment(request, post_id, comment_id):
    post = _visible_post(request, post_id)
    comment = get_object_or_404(Comment, pk=comment_id, post=post)
    if comment.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {'comment': comment})
